import logging
import httpx
import pytest
from sqlalchemy import select
from app.core.config import get_settings
from app.core.security import digest, now
from app.models.auth import User
from app.models.whatsapp_official import WhatsAppSignupAttempt, WhatsAppOfficialConnection
from tests.test_whatsapp_official import configure, meta, TOKEN, PAYLOAD, PREFIX

CODE = 'test-only-authorization-code-abcdefghijklmnopqrstuvwxyz'

def prepare(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv('WHATSAPP_EMBEDDED_CONFIG_ID', '88888')
    get_settings.cache_clear()
    calls, state = meta(monkeypatch)
    # Wrap the same transport so exchange AND validation execute real service logic.
    client_factory = httpx.Client
    def factory(**kwargs):
        client = client_factory(**kwargs)
        original = client.get
        def get(url, **args):
            if str(url).endswith('/oauth/access_token'):
                request = httpx.Request('GET', url, params=args['params'])
                calls.append(request)
                return httpx.Response(200, json={'access_token': TOKEN}, request=request)
            return original(url, **args)
        client.get = get
        return client
    monkeypatch.setattr(httpx, 'Client', factory)
    return calls

def start(client):
    result = client.post(PREFIX+'/embedded/start', json={'version': 0})
    assert result.status_code == 200, result.text
    return result.json()['state']

def body(state):
    return {'state': state, 'code': CODE, 'phone_number_id': '12345', 'waba_id': '67890'}

def test_signup_exchange_encrypts_no_secrets_replay_and_version(client, database, signup, monkeypatch, caplog):
    calls = prepare(monkeypatch)
    identity = client.post('/api/v1/auth/register', json=signup).json()
    config = client.get(PREFIX+'/embedded/config').json()
    assert config['enabled'] and config['config_id'] == '88888'
    assert 'test-only-app-secret' not in str(config)
    state = start(client)
    with caplog.at_level(logging.DEBUG):
        response = client.post(PREFIX+'/embedded/complete', json=body(state))
    assert response.status_code == 200, response.text
    assert response.json()['has_token'] and response.json()['version'] == 1
    for secret in [TOKEN, CODE, state, 'test-only-app-secret']:
        assert secret not in response.text and secret not in caplog.text
    assert sum(str(r.url.path).endswith('/oauth/access_token') for r in calls) == 1
    with database() as db:
        attempt = db.get(WhatsAppSignupAttempt, digest(state))
        assert attempt.consumed and attempt.code_hash == digest(CODE)
        assert TOKEN not in db.get(WhatsAppOfficialConnection, identity['company']['id']).encrypted_token
    assert client.post(PREFIX+'/embedded/complete', json=body(state)).status_code == 409
    assert sum(str(r.url.path).endswith('/oauth/access_token') for r in calls) == 1


def test_signup_bound_to_company_session_expiry_and_csrf(client, database, signup, monkeypatch):
    prepare(monkeypatch)
    first = client.post('/api/v1/auth/register', json=signup).json()
    state = start(client)
    # Same user but another login cannot complete an old browser-session attempt.
    client.post('/api/v1/auth/login', json={'email': signup['email'], 'password': signup['password']})
    assert client.post(PREFIX+'/embedded/complete', json=body(state)).status_code == 409
    client.post('/api/v1/auth/register', json={**signup, 'email': 'other@example.com'})
    assert client.post(PREFIX+'/embedded/complete', json=body(state)).status_code == 409
    other_state = start(client)
    with database() as db:
        attempt = db.get(WhatsAppSignupAttempt, digest(other_state)); attempt.expires_at = now()-1; db.commit()
    assert client.post(PREFIX+'/embedded/complete', json=body(other_state)).status_code == 409
    assert client.post(PREFIX+'/embedded/start', json={'version': 0}, headers={'Origin': 'https://evil.example'}).status_code == 403
    assert client.post(PREFIX+'/embedded/start', json={'version': 0, 'company_id': first['company']['id']}).status_code == 422


def test_configuration_permissions_and_consumed_on_failure(client, database, signup, monkeypatch):
    configure(monkeypatch)
    client.post('/api/v1/auth/register', json=signup)
    assert client.get(PREFIX+'/embedded/config').json()['enabled'] is False
    assert client.post(PREFIX+'/embedded/start', json={'version': 0}).status_code == 503
    prepare(monkeypatch)
    state = start(client)
    from app.integrations import whatsapp_official
    from fastapi import HTTPException
    def failure(code): raise HTTPException(422, 'Autorização recusada.')
    monkeypatch.setattr(whatsapp_official, 'exchange_signup_code', failure)
    assert client.post(PREFIX+'/embedded/complete', json=body(state)).status_code == 422
    assert client.post(PREFIX+'/embedded/complete', json=body(state)).status_code == 409
    with database() as db:
        assert db.scalar(select(WhatsAppOfficialConnection)) is None
        user = db.scalar(select(User)); user.role = 'seller'; db.commit()
    assert client.get(PREFIX+'/embedded/config').status_code == 403
    assert client.post(PREFIX+'/embedded/start', json={'version': 0}).status_code == 403


def test_stale_connection_and_global_code_reuse(client, database, signup, monkeypatch):
    prepare(monkeypatch)
    client.post('/api/v1/auth/register', json=signup)
    state = start(client)
    second = start(client)
    assert client.post(PREFIX+'/embedded/complete', json=body(state)).status_code == 200
    assert client.post(PREFIX+'/embedded/complete', json=body(second)).status_code == 409
    client.post('/api/v1/auth/register', json={**signup, 'email': 'second@example.com'})
    assert client.post(PREFIX+'/embedded/complete', json=body(start(client))).status_code == 409


@pytest.mark.parametrize('mode', ['invalid', 'timeout', 'malformed', 'redirect'])
def test_exchange_failure_sanitized(monkeypatch, mode):
    configure(monkeypatch)
    from app.integrations.whatsapp_official import exchange_signup_code
    from fastapi import HTTPException
    original = httpx.Client
    def handle(request):
        if mode == 'timeout': raise httpx.ReadTimeout(CODE)
        if mode == 'invalid': return httpx.Response(400, json={'error': {'message': CODE}})
        if mode == 'redirect': return httpx.Response(302, headers={'Location': 'https://evil.example'})
        return httpx.Response(200, json={'access_token': '\n'+TOKEN})
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs))
    with pytest.raises(HTTPException) as exc: exchange_signup_code(CODE)
    assert CODE not in str(exc.value) and TOKEN not in str(exc.value)


def test_concurrent_completions_exchange_only_once(client, database, signup, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    calls = prepare(monkeypatch)
    client.post('/api/v1/auth/register', json=signup)
    state = start(client)
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda _: client.post(PREFIX+'/embedded/complete', json=body(state)).status_code, range(2)))
    assert sorted(results) == [200, 409]
    assert sum(r.url.path.endswith('/oauth/access_token') for r in calls) == 1
