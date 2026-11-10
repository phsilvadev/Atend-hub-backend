import base64
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
import httpx
import pytest
from sqlalchemy import select
from app.models.knowledge import PlatformAdmin,PlatformControl,PlatformOpenAI,PlatformSession,PlatformAudit
from app.core.security import passwords
from app.core.config import get_settings
from app.services import platform_settings as service
from app.services.platform_auth import bootstrap,PLATFORM_COOKIE
from tests.test_shared_knowledge import platform_login,PASSWORD,ROOT

ADMIN=ROOT+'/administrators'
AI=ROOT+'/settings/openai'
NEW_PASSWORD='Senha-admin-secundario-123!'
KEY='sk-unit-test-only-'+'x'*40

def new_admin(client,**extra):
    return client.post(ADMIN,json={'name':'Ana Souza','email':'ana@example.com','password':NEW_PASSWORD,'current_password':PASSWORD,**extra})

def edits(row,confirmation=PASSWORD,**extra):
    return {'version':row['version'],'name':row['name'],'email':row['email'],'active':row['active'],'current_password':confirmation,**extra}


def test_root_protected_against_secondary_and_unknown_fields(client,database):
    root_id=platform_login(client,database)
    root=client.get(ADMIN).json()['items'][0]
    assert root['is_primary'] and root['can_edit'] and not root['can_deactivate']
    assert client.patch(ADMIN+'/'+root_id,json=edits(root,active=False)).status_code==403
    added=new_admin(client)
    assert added.status_code==201,added.text
    secondary=added.json()
    assert not secondary['is_primary'] and secondary['active']
    assert client.post(ADMIN,json={'name':'Fake root','email':'fake@example.com','password':NEW_PASSWORD,'current_password':PASSWORD,'is_primary':True}).status_code==422
    assert client.patch(ADMIN+'/'+root_id,json={**edits(root),'primary_admin_id':secondary['id']}).status_code==422
    client.cookies.clear()
    assert client.post(ROOT+'/auth/login',json={'email':'ana@example.com','password':NEW_PASSWORD}).status_code==200
    listed=client.get(ADMIN).json()['items'];visible_root=next(r for r in listed if r['id']==root_id)
    assert visible_root['is_primary'] and not visible_root['can_edit'] and not visible_root['can_deactivate']
    for changes in ({'password':'Tentativa-de-senha-invasora-123'},{'active':False},{'email':'taken@example.com'},{'name':'Outra identidade'}):
        assert client.patch(ADMIN+'/'+root_id,json=edits(root,confirmation=NEW_PASSWORD,**changes)).status_code==403
    assert client.delete(ADMIN+'/'+root_id).status_code==405
    assert client.get(AI).json()['can_manage'] is True
    with database() as db:
        protected=db.get(PlatformAdmin,root_id)
        assert passwords.verify(PASSWORD,protected.password_hash) and protected.active and protected.email=='platform@example.com'
        assert db.get(PlatformControl,1).primary_admin_id==root_id


def test_primary_can_change_own_password_and_sessions_are_revoked(client,database):
    root_id=platform_login(client,database);token=client.cookies.get(PLATFORM_COOKIE)
    root=client.get(ADMIN).json()['items'][0]
    changed=client.patch(ADMIN+'/'+root_id,json=edits(root,**{'password':'Nova-senha-primaria-123!'}))
    assert changed.status_code==200 and changed.json()['requires_login']
    assert client.get(ADMIN).status_code==401
    client.cookies.clear()
    assert client.post(ROOT+'/auth/login',json={'email':root['email'],'password':PASSWORD}).status_code==401
    assert client.post(ROOT+'/auth/login',json={'email':root['email'],'password':'Nova-senha-primaria-123!'}).status_code==200
    client.cookies.set(PLATFORM_COOKIE,token)
    assert client.get(ADMIN).status_code==401


def test_confirmation_duplicates_versions_and_reactivation(client,database):
    platform_login(client,database)
    assert new_admin(client,current_password='wrong').status_code==403
    assert new_admin(client,password='short').status_code==422
    added=new_admin(client).json()
    assert new_admin(client).status_code==409
    assert client.patch(ADMIN+'/'+added['id'],json=edits(added,version=99)).status_code==409
    assert client.patch(ADMIN+'/'+added['id'],json=edits(added,current_password='wrong')).status_code==403
    disabled=client.patch(ADMIN+'/'+added['id'],json=edits(added,active=False)).json()
    assert not disabled['active']
    assert client.post(ROOT+'/auth/login',json={'email':added['email'],'password':NEW_PASSWORD}).status_code==401
    assert client.patch(ADMIN+'/'+added['id'],json=edits(disabled,active=True)).status_code==200
    assert client.get(ADMIN,params={'q':'ana@','offset':0,'limit':1}).json()['total']==1
    assert client.get(ADMIN,params={'q':'%'}).json()['items']==[]
    assert client.get(ADMIN,params={'offset':99}).json()['items']==[]


def test_secondary_self_disable_refused_and_password_reset_revokes_sessions(client,database):
    platform_login(client,database);root_token=client.cookies.get(PLATFORM_COOKIE)
    added=new_admin(client).json();client.cookies.clear()
    client.post(ROOT+'/auth/login',json={'email':added['email'],'password':NEW_PASSWORD});secondary_token=client.cookies.get(PLATFORM_COOKIE)
    assert client.patch(ADMIN+'/'+added['id'],json=edits(added,confirmation=NEW_PASSWORD,active=False)).status_code==403
    client.cookies.clear();client.cookies.set(PLATFORM_COOKIE,root_token)
    result=client.patch(ADMIN+'/'+added['id'],json=edits(added,**{'password':'Outra-senha-secundaria-123!'}))
    assert result.status_code==200
    client.cookies.clear();client.cookies.set(PLATFORM_COOKIE,secondary_token)
    assert client.get(ADMIN).status_code==401


def test_platform_routes_block_tenant_and_anonymous(client,database,signup):
    for path in [ADMIN,AI]:assert client.get(path).status_code==401
    client.post('/api/v1/auth/register',json=signup)
    assert client.get(ADMIN).status_code==401 and client.get(AI).status_code==401
    assert client.post(ADMIN,json={'name':'Tenant root','email':'x@example.com','password':NEW_PASSWORD,'current_password':signup['password']}).status_code==401


@pytest.fixture
def secret_storage(monkeypatch):
    monkeypatch.setenv('PLATFORM_CREDENTIAL_KEY',base64.urlsafe_b64encode(b'test-only-master-key-for-platform'[:32]).decode())
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def save_ai(client,version=1,**extra):
    return client.patch(AI,json={'version':version,'model':'gpt-4.1-mini','api_key':KEY,'current_password':PASSWORD,**extra})


def test_openai_secret_encrypted_write_only_rotation_remove_and_version(client,database,secret_storage):
    platform_login(client,database)
    start=client.get(AI).json();assert start['storage_ready'] and not start['configured']
    saved=save_ai(client)
    assert saved.status_code==200,saved.text
    config=saved.json();assert config['configured'] and KEY not in saved.text and 'key_ciphertext' not in saved.text
    with database() as db:
        row=db.get(PlatformOpenAI,1);assert KEY not in row.key_ciphertext and service.decrypt(row.key_ciphertext)==KEY
        audits=json.dumps([{'action':r.action,'target':r.target_id} for r in db.scalars(select(PlatformAudit))]);assert KEY not in audits
    assert save_ai(client).status_code==409
    updated=client.patch(AI,json={'version':config['version'],'model':'gpt-4.1','current_password':PASSWORD})
    assert updated.status_code==200 and updated.json()['configured']
    action={'version':updated.json()['version'],'current_password':PASSWORD}
    removed=client.post(AI+'/remove',json=action)
    assert removed.status_code==200 and not removed.json()['configured']
    assert client.post(AI+'/test',json={'version':removed.json()['version'],'current_password':PASSWORD}).status_code==422
    with database() as db:assert db.get(PlatformOpenAI,1).key_ciphertext is None


def test_openai_missing_storage_no_echo_or_http_call(client,database,monkeypatch):
    monkeypatch.setenv('PLATFORM_CREDENTIAL_KEY','');get_settings.cache_clear()
    platform_login(client,database)
    assert not client.get(AI).json()['storage_ready']
    response=save_ai(client)
    assert response.status_code==503 and KEY not in response.text
    assert save_ai(client,api_key='bad key').status_code==422
    assert save_ai(client,model='../../admin').status_code==422
    assert save_ai(client,current_password='wrong').status_code==403


def test_openai_diagnostic_contract_and_sanitized_provider_failures(client,database,secret_storage):
    platform_login(client,database)
    config=save_ai(client).json()
    def transport(request):
        assert request.method=='GET' and str(request.url)=='https://api.openai.com/v1/models/gpt-4.1-mini'
        assert request.headers['Authorization']=='Bearer '+KEY
        return httpx.Response(200,json={'id':'gpt-4.1-mini'})
    actual=httpx.Client
    with patch.object(service.httpx,'Client',side_effect=lambda **kw:actual(transport=httpx.MockTransport(transport),trust_env=False,**kw)):
        tested=client.post(AI+'/test',json={'version':config['version'],'current_password':PASSWORD})
    assert tested.status_code==200 and tested.json()['check_status']=='verified' and tested.json()['checked_at']
    for code,status in [(401,'invalid_key'),(403,'forbidden'),(404,'model_unavailable'),(429,'rate_limited'),(500,'unavailable'),(302,'unavailable')]:
        with patch.object(service.httpx,'Client',side_effect=lambda **kw:actual(transport=httpx.MockTransport(lambda req:httpx.Response(code,json={'error':{'message':KEY}})),trust_env=False,**kw)):
            result=client.post(AI+'/test',json={'version':tested.json()['version'],'current_password':PASSWORD})
        assert result.status_code==200 and result.json()['check_status']==status and KEY not in result.text
        tested=result


def test_openai_probe_timeout_and_malformed_response():
    actual=httpx.Client
    def timeout(req):raise httpx.ReadTimeout('DO_NOT_EXPOSE_PROVIDER_SECRETS')
    with patch.object(service.httpx,'Client',side_effect=lambda **kw:actual(transport=httpx.MockTransport(timeout),trust_env=False,**kw)):
        assert service.probe_model(KEY,'gpt-4.1-mini')=='unavailable'
    with patch.object(service.httpx,'Client',side_effect=lambda **kw:actual(transport=httpx.MockTransport(lambda req:httpx.Response(200,text='not-json')),trust_env=False,**kw)):
        assert service.probe_model(KEY,'gpt-4.1-mini')=='unavailable'


def test_duplicate_admin_creation_race_keeps_primary_and_unique_email(client,database):
    primary_id=platform_login(client,database)
    from app.schemas.platform_settings import AdminCreate
    from app.services.platform_auth import PlatformContext
    from app.core.security import digest
    token=client.cookies.get(PLATFORM_COOKIE)
    gate=Barrier(2)
    def create():
        with database() as db:
            admin=db.get(PlatformAdmin,primary_id);session=db.get(PlatformSession,digest(token));gate.wait()
            try:
                service.create_admin(db,PlatformContext(admin,session),AdminCreate(name='Concurrent Admin',email='same@example.com',password=NEW_PASSWORD,current_password=PASSWORD))
                return 201
            except Exception as error:
                db.rollback();return getattr(error,'status_code',500)
    with ThreadPoolExecutor(max_workers=2) as pool:statuses=list(pool.map(lambda _:create(),range(2)))
    assert sorted(statuses) in ([201,409],[201,429]),statuses
    with database() as db:
        assert len(list(db.scalars(select(PlatformAdmin).where(PlatformAdmin.email=='same@example.com'))))==1
        assert db.get(PlatformControl,1).primary_admin_id==primary_id


def test_login_verified_old_password_cannot_recreate_session_after_change(client,database,monkeypatch):
    from app.services import platform_auth
    root_id=platform_login(client,database)
    original=platform_auth.verify_password
    def interleaved(password,stored):
        valid=original(password,stored)
        if valid:
            with database() as db:
                row=db.get(PlatformAdmin,root_id);row.password_hash=passwords.hash('Password-rotated-during-login-123!');row.version+=1
                db.execute(__import__('sqlalchemy').update(PlatformSession).where(PlatformSession.admin_id==root_id).values(revoked=True));db.commit()
        return valid
    monkeypatch.setattr(platform_auth,'verify_password',interleaved)
    assert client.post(ROOT+'/auth/login',json={'email':'platform@example.com','password':PASSWORD}).status_code==401


def test_diagnostic_cannot_validate_a_rotated_configuration(client,database,secret_storage,monkeypatch):
    platform_login(client,database);config=save_ai(client).json()
    def interleaved(key,model):
        with database() as db:
            row=db.get(PlatformOpenAI,1);row.model='gpt-4.1';row.version+=1;db.commit()
        return 'verified'
    monkeypatch.setattr(service,'probe_model',interleaved)
    result=client.post(AI+'/test',json={'version':config['version'],'current_password':PASSWORD})
    assert result.status_code==409
    with database() as db:assert db.get(PlatformOpenAI,1).check_status is None


def test_secondary_can_manage_openai_without_touching_primary(client,database,secret_storage):
    primary_id=platform_login(client,database)
    secondary=new_admin(client).json()
    client.cookies.clear();client.post(ROOT+'/auth/login',json={'email':secondary['email'],'password':NEW_PASSWORD})
    saved=save_ai(client,current_password=NEW_PASSWORD)
    assert saved.status_code==200 and saved.json()['can_manage'] and saved.json()['configured']
    with patch.object(service,'probe_model',return_value='verified'):
        tested=client.post(AI+'/test',json={'version':saved.json()['version'],'current_password':NEW_PASSWORD})
    assert tested.status_code==200 and tested.json()['check_status']=='verified'
    removed=client.post(AI+'/remove',json={'version':tested.json()['version'],'current_password':NEW_PASSWORD})
    assert removed.status_code==200 and not removed.json()['configured']
    with database() as db:assert db.get(PlatformAdmin,primary_id).active


def test_migration_preserves_existing_first_admin_identity(database):
    from alembic import command
    from alembic.config import Config
    with database() as db:
        first=bootstrap(db,'Primeiro','first@example.com',PASSWORD)
        first_id=first.id
        bootstrap(db,'Segundo','second@example.com',NEW_PASSWORD)
        for row in db.scalars(select(PlatformAudit).where(PlatformAudit.action=='platform.admin.created')):
            row.created_at=10 if row.admin_id==first_id else 20
        db.commit()
    command.downgrade(Config('alembic.ini'),'20261109_client_auth')
    command.upgrade(Config('alembic.ini'),'head')
    with database() as db:
        assert db.get(PlatformControl,1).primary_admin_id==first_id
        assert passwords.verify(PASSWORD,db.get(PlatformAdmin,first_id).password_hash)
