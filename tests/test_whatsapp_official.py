import base64
import json
import logging
import pytest
import httpx
from sqlalchemy import select
from fastapi import HTTPException
from app.core.config import get_settings
from app.core.security import now
from app.core.integration_secrets import decrypt_token,encrypt_token
from app.api import whatsapp_official as api
from app.models.auth import User,AuditEvent
from app.models.whatsapp import WhatsAppNumber
from app.models.whatsapp_official import WhatsAppOfficialConnection as Connection

PREFIX='/api/v1/integrations/whatsapp-official'
TOKEN='test-only-meta-token-abcdefghijklmnopqrstuvwxyz'
KEY=base64.urlsafe_b64encode(b'a'*32).decode()
PAYLOAD={'phone_number_id':'12345','waba_id':'67890','version':0,'access_token':TOKEN}

def configure(monkeypatch):
    monkeypatch.setenv('WHATSAPP_CREDENTIAL_KEY',KEY)
    monkeypatch.setenv('WHATSAPP_APP_ID','55555')
    monkeypatch.setenv('WHATSAPP_APP_SECRET','test-only-app-secret')
    monkeypatch.setenv('WHATSAPP_VERIFY_TOKEN','test-only-verify')
    monkeypatch.setenv('WHATSAPP_PUBLIC_WEBHOOK_URL','https://api.example.com/api/v1/webhooks/whatsapp')
    get_settings.cache_clear()

def meta(monkeypatch,mode='ok'):
    calls=[]
    original=httpx.Client
    state={'status':'CONNECTED','subscribed':False}
    def handler(request):
        calls.append(request)
        assert request.url.host=='graph.facebook.com'
        path=request.url.path
        if mode=='invalid':
            return httpx.Response(401,json={'error':{'message':TOKEN}})
        if mode=='timeout':
            raise httpx.ReadTimeout(TOKEN)
        if path.endswith('/phone_numbers'):
            data={'data':[{'id':state.get('phone_id','12345'),'display_phone_number':'+55 11 99999-0000','verified_name':'Empresa teste'}] if mode!='wrong-phone' else []}
        elif path.endswith('/debug_token'):
            data={'data':{'is_valid':True,'app_id':'55555' if mode!='wrong-app' else '99999','scopes':['whatsapp_business_management','whatsapp_business_messaging'],'expires_at':now()+86400}}
        elif path.endswith('/subscribed_apps'):
            if request.method=='POST':state['subscribed']=True;data={'success':True}
            else:data={'data':[{'whatsapp_business_api_data':{'id':'55555'}}] if state['subscribed'] else []}
        elif path.endswith('/register'):
            state['status']='CONNECTED';data={'success':True}
        elif path.endswith('/12345'):
            data={'id':'12345','status':state['status'],'code_verification_status':'VERIFIED','platform_type':'CLOUD_API'}
        else:raise AssertionError(path)
        return httpx.Response(200,json=data)
    def client(**kwargs):return original(transport=httpx.MockTransport(handler),**kwargs)
    monkeypatch.setattr(api.validate_credentials.__globals__['httpx'],'Client',client)
    return calls,state

def test_encrypted_at_rest_no_secret_returned_and_tenant_bound(client,database,signup,monkeypatch,caplog):
    configure(monkeypatch);calls,_=meta(monkeypatch)
    identity=client.post('/api/v1/auth/register',json=signup).json()
    with caplog.at_level(logging.DEBUG):
        result=client.post(PREFIX+'/connect',json=PAYLOAD)
    assert result.status_code==200
    response=result.json();assert response['status']=='validated' and response['has_token'] is True
    assert response['diagnostics']['app_confirmed'] is True
    assert TOKEN not in result.text and 'encrypted_token' not in result.text and KEY not in result.text
    assert TOKEN not in caplog.text
    with database() as db:
        saved=db.get(Connection,identity['company']['id'])
        assert TOKEN not in saved.encrypted_token and saved.encrypted_token.startswith('v1:')
        assert decrypt_token(saved.encrypted_token,saved.company_id,saved.phone_number_id,saved.waba_id)==TOKEN
        with pytest.raises(HTTPException):decrypt_token(saved.encrypted_token,'other-tenant',saved.phone_number_id,saved.waba_id)
        assert all(TOKEN not in event.action for event in db.scalars(select(AuditEvent)))
    assert client.get(PREFIX).json()['has_token'] is True
    # Empty token reuses protected credentials without returning them to the browser.
    again=client.post(PREFIX+'/connect',json={**{key:value for key,value in PAYLOAD.items() if key!='access_token'},'version':1})
    assert again.status_code==200 and TOKEN not in again.text
    assert client.post(PREFIX+'/connect',json={**PAYLOAD,'version':0}).status_code==409
    assert all(request.headers['authorization'].startswith('Bearer ') for request in calls)

@pytest.mark.parametrize('mode',['invalid','wrong-phone','wrong-app','timeout'])
def test_invalid_credentials_never_saved_or_echoed(client,database,signup,monkeypatch,mode):
    configure(monkeypatch);meta(monkeypatch,mode)
    client.post('/api/v1/auth/register',json=signup)
    response=client.post(PREFIX+'/connect',json=PAYLOAD)
    assert response.status_code in (422,503)
    assert TOKEN not in response.text
    with database() as db:
        assert db.scalar(select(Connection)) is None
        assert db.get(WhatsAppNumber,'12345') is None


def test_permissions_encryption_required_and_tenant_override_rejected(client,database,signup,monkeypatch):
    configure(monkeypatch)
    assert client.get(PREFIX).status_code==401
    identity=client.post('/api/v1/auth/register',json=signup).json()
    assert client.post(PREFIX+'/connect',json={**PAYLOAD,'company_id':'forged'}).status_code==422
    assert client.post(PREFIX+'/connect',json={**PAYLOAD,'access_token':'bad\nheader'}).status_code==422
    monkeypatch.setenv('WHATSAPP_CREDENTIAL_KEY','');get_settings.cache_clear()
    assert client.get(PREFIX).json()['enabled'] is False
    assert client.post(PREFIX+'/connect',json=PAYLOAD).status_code==503
    with database() as db:
        db.get(User,identity['user']['id']).role='seller';db.commit()
    assert client.get(PREFIX).status_code==403
    assert client.post(PREFIX+'/connect',json=PAYLOAD).status_code==403
    assert client.post(PREFIX+'/disconnect',json={'version':0}).status_code==403
    assert client.post(PREFIX+'/setup',json={'version':0,'action':'subscribe','confirm':True}).status_code==403


def test_other_company_cannot_claim_number_or_read_metadata(client,database,signup,monkeypatch):
    configure(monkeypatch);meta(monkeypatch)
    a=client.post('/api/v1/auth/register',json=signup).json()
    assert client.post(PREFIX+'/connect',json=PAYLOAD).status_code==200
    client.post('/api/v1/auth/logout',json={})
    b=client.post('/api/v1/auth/register',json={**signup,'email':'b@example.com','company':'Empresa B'}).json()
    response=client.get(PREFIX).json();assert response['company_id']==b['company']['id'] and response['phone_number_id']=='' and not response['has_token']
    assert client.post(PREFIX+'/connect',json=PAYLOAD).status_code==409
    assert client.post(PREFIX+'/disconnect',json={'version':0}).status_code==200
    with database() as db:
        assert db.get(Connection,a['company']['id']).active


def test_setup_confirmation_and_disconnect_erases_token_and_blocks_route(client,database,signup,monkeypatch):
    configure(monkeypatch);calls,state=meta(monkeypatch)
    identity=client.post('/api/v1/auth/register',json=signup).json()
    assert client.post(PREFIX+'/connect',json=PAYLOAD).status_code==200
    assert client.post(PREFIX+'/setup',json={'action':'subscribe','version':1,'confirm':False}).status_code==422
    subscribed=client.post(PREFIX+'/setup',json={'action':'subscribe','version':1,'confirm':True})
    assert subscribed.status_code==200 and subscribed.json()['diagnostics']['app_subscribed'] is True
    assert client.post(PREFIX+'/setup',json={'action':'register','version':2,'confirm':True,'pin':'notvalid'}).status_code==422
    # Explicit registration, with transient PIN and no PIN in persisted diagnostics.
    state['status']='PENDING'
    registered=client.post(PREFIX+'/setup',json={'action':'register','version':2,'confirm':True,'pin':'123456'})
    assert registered.status_code==200 and registered.json()['diagnostics']['phone_status']=='CONNECTED'
    assert '123456' not in registered.text
    removed=client.post(PREFIX+'/disconnect',json={'version':3})
    assert removed.status_code==200 and removed.json()['has_token'] is False
    with database() as db:
        row=db.get(Connection,identity['company']['id']);assert row.encrypted_token is None and not row.active
        assert not db.get(WhatsAppNumber,'12345').active
    assert client.post(PREFIX+'/connect',json={'version':4,'phone_number_id':'12345','waba_id':'67890'}).status_code==422

def test_revoked_admin_during_validation_cannot_persist(client,database,signup,monkeypatch):
    configure(monkeypatch)
    identity=client.post('/api/v1/auth/register',json=signup).json()
    def revoked(*args):
        with database() as db:
            db.get(User,identity['user']['id']).role='seller';db.commit()
        return {'display_phone_number':'+5511999999999','verified_name':'Teste','diagnostics':{}}
    monkeypatch.setattr(api,'validate_credentials',revoked)
    assert client.post(PREFIX+'/connect',json=PAYLOAD).status_code==403
    with database() as db:
        assert db.get(Connection,identity['company']['id']) is None


def test_cipher_tamper_wrong_key_and_nonce_rotation(database,monkeypatch):
    configure(monkeypatch)
    first=encrypt_token(TOKEN,'tenant','phone','waba')
    second=encrypt_token(TOKEN,'tenant','phone','waba')
    assert first!=second
    with pytest.raises(HTTPException):decrypt_token(first,'tenant','other-phone','waba')
    with pytest.raises(HTTPException):decrypt_token(first[:-6]+'AAAAAA','tenant','phone','waba')
    monkeypatch.setenv('WHATSAPP_CREDENTIAL_KEY',base64.urlsafe_b64encode(b'b'*32).decode());get_settings.cache_clear()
    with pytest.raises(HTTPException):decrypt_token(first,'tenant','phone','waba')

def test_development_key_cli_does_not_print_or_overwrite_secret(tmp_path,monkeypatch,capsys):
    from app.cli import integration_key
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('APP_ENV','development')
    monkeypatch.setenv('WHATSAPP_CREDENTIAL_KEY','')
    get_settings.cache_clear()
    integration_key.main()
    secret_line=(tmp_path/'.env').read_text()
    assert 'WHATSAPP_CREDENTIAL_KEY=' in secret_line
    assert secret_line.strip().split('=',1)[1] not in capsys.readouterr().out
    assert (tmp_path/'.env').stat().st_mode & 0o077 == 0
    monkeypatch.delenv('WHATSAPP_CREDENTIAL_KEY')
    get_settings.cache_clear()
    integration_key.main()
    assert (tmp_path/'.env').read_text()==secret_line
    get_settings.cache_clear()


def test_setup_rechecks_phone_membership_before_mutating_meta(client,database,signup,monkeypatch):
    configure(monkeypatch);calls,state=meta(monkeypatch)
    client.post('/api/v1/auth/register',json=signup)
    assert client.post(PREFIX+'/connect',json=PAYLOAD).status_code==200
    state['phone_id']='number-moved-to-other-account'
    assert client.post(PREFIX+'/setup',json={'action':'subscribe','version':1,'confirm':True}).status_code==422
    assert not any(request.method=='POST' for request in calls)
