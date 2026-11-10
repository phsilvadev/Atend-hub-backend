from datetime import datetime, timezone, timedelta
import json
import httpx
import pytest
from sqlalchemy import select, func
from pydantic import ValidationError
from app.core.config import get_settings, Settings
from app.services import turnstile
from app.services.platform_auth import bootstrap
from app.models.auth import Company, Session, ChallengeUse
from app.models.knowledge import PlatformSession

SECRET = 'unit-test-server-secret-never-log'
TOKEN = 'unit-test-challenge-token-never-log'
ORIGINAL_CLIENT = httpx.Client

def configure(monkeypatch, result=None, status=200, timeout=False):
    monkeypatch.setenv('TURNSTILE_ENABLED', 'true')
    monkeypatch.setenv('TURNSTILE_TESTING', 'false')
    monkeypatch.setenv('TURNSTILE_SITE_KEY', 'unit-site-key')
    monkeypatch.setenv('TURNSTILE_SECRET_KEY', SECRET)
    monkeypatch.setenv('TURNSTILE_ALLOWED_HOSTNAMES', '["app.example.com","admin.example.com"]')
    get_settings.cache_clear()
    calls = []
    def handler(request):
        assert str(request.url) == turnstile.SITEVERIFY and request.method == 'POST'
        assert SECRET.encode() in request.content and TOKEN.encode() in request.content
        calls.append(request)
        if timeout: raise httpx.ReadTimeout(SECRET)
        return httpx.Response(status, json=result if result is not None else success())
    monkeypatch.setattr(turnstile.httpx, 'Client', lambda **kwargs: ORIGINAL_CLIENT(transport=httpx.MockTransport(handler), **kwargs))
    return calls

def success(action='client_register', hostname='app.example.com', age=0):
    return {'success':True, 'action':action, 'hostname':hostname, 'challenge_ts':(datetime.now(timezone.utc)-timedelta(seconds=age)).isoformat()}

def test_register_requires_server_verification_and_persistent_single_use(client, database, signup, monkeypatch):
    calls = configure(monkeypatch)
    assert client.post('/api/v1/auth/register', json=signup).status_code == 403
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Company)) == 0
    result = client.post('/api/v1/auth/register', json={**signup,'challenge_token':TOKEN})
    assert result.status_code == 201 and 'challenge_token' not in result.text and SECRET not in result.text
    assert client.post('/api/v1/auth/register', json={**signup,'email':'other@example.com','challenge_token':TOKEN}).status_code == 403
    assert len(calls) == 1
    with database() as db:
        saved = db.scalar(select(ChallengeUse))
        assert saved.token_hash != TOKEN and len(saved.token_hash) == 64
        assert db.scalar(select(func.count()).select_from(Company)) == 1

@pytest.mark.parametrize('payload,status,timeout,expected', [
    ({'success':False,'error-codes':['timeout-or-duplicate']},200,False,403),
    ({'success':False,'error-codes':[SECRET]},200,False,403),
    (success(action='platform_login'),200,False,403),
    (success(hostname='attacker.example'),200,False,403),
    (success(age=301),200,False,403),
    (lambda: success(age=-120),200,False,403),
    ({'success':True},200,False,403),
    ({'success':'true'},200,False,403),
    ({},500,False,503),
    ({},200,True,503),
])
def test_invalid_provider_result_never_registers_or_leaks(client, database, signup, monkeypatch, payload, status, timeout, expected):
    if callable(payload): payload=payload()  # Timestamp relative to this test, not collection time.
    configure(monkeypatch,payload,status,timeout)
    result=client.post('/api/v1/auth/register',json={**signup,'challenge_token':TOKEN})
    assert result.status_code == expected and TOKEN not in result.text and SECRET not in result.text
    assert 'set-cookie' not in result.headers
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Company)) == 0
        assert db.scalar(select(func.count()).select_from(Session)) == 0


def test_tenant_login_rejects_missing_challenge_even_with_correct_password(client, signup, monkeypatch):
    assert client.post('/api/v1/auth/register',json=signup).status_code == 201
    client.post('/api/v1/auth/logout')
    configure(monkeypatch,success(action='client_login'))
    body={'email':signup['email'],'password':signup['password']}
    assert client.post('/api/v1/auth/login',json=body).status_code == 403
    assert client.post('/api/v1/auth/login',json={**body,'challenge_token':TOKEN}).status_code == 200


def test_platform_login_and_public_configuration(client, database, monkeypatch):
    with database() as db: bootstrap(db,'Plataforma','platform@example.com','Senha-plataforma-123!')
    configure(monkeypatch,success(action='platform_login',hostname='admin.example.com'))
    for path in ['/api/v1/auth/challenge','/api/v1/platform/auth/challenge']:
        result=client.get(path)
        assert result.status_code == 200 and result.json()=={'enabled':True,'site_key':'unit-site-key','testing':False}
        assert SECRET not in result.text
    body={'email':'platform@example.com','password':'Senha-plataforma-123!'}
    assert client.post('/api/v1/platform/auth/login',json=body).status_code == 403
    with database() as db: assert db.scalar(select(func.count()).select_from(PlatformSession)) == 0
    assert client.post('/api/v1/platform/auth/login',json={**body,'challenge_token':TOKEN}).status_code == 200


def test_token_never_replaces_password(client, signup, monkeypatch):
    assert client.post('/api/v1/auth/register',json=signup).status_code == 201
    client.post('/api/v1/auth/logout')
    configure(monkeypatch,success(action='client_login'))
    result=client.post('/api/v1/auth/login',json={'email':signup['email'],'password':'incorrect','challenge_token':TOKEN})
    assert result.status_code == 401 and 'set-cookie' not in result.headers
    assert client.post('/api/v1/auth/login',json={'email':signup['email'],'password':signup['password'],'challenge_token':TOKEN}).status_code == 403


def test_production_cannot_disable_challenge_or_use_public_test_keys():
    base=dict(_env_file=None,app_env='production',cookie_secure=True,database_url='postgresql+psycopg://test@localhost/db',allowed_origins=['https://app.example.com'])
    for settings in [{},{'turnstile_enabled':True,'turnstile_testing':True,'turnstile_site_key':turnstile.TEST_SITE_KEY,'turnstile_secret_key':turnstile.TEST_SECRET_KEY}]:
        with pytest.raises(ValidationError):Settings(**base,**settings)
    assert Settings(**base,turnstile_enabled=True,turnstile_site_key='real-style-site-key',turnstile_secret_key=SECRET,turnstile_allowed_hostnames=['app.example.com']).turnstile_enabled
