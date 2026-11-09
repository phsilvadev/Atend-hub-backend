import base64
import json
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import pytest
from sqlalchemy import select
from app.core.config import get_settings
from app.core.security import now, digest, verify_password
from app.models.auth import GoogleIdentity, User, Company, PasswordReset
from app.services import client_auth

GOOGLE = '/api/v1/auth/google'
PASSWORD = '/api/v1/auth/password'
CREDENTIAL = 'test-only-google-credential-' + 'a'*120

def configure(monkeypatch):
    monkeypatch.setenv('GOOGLE_AUTH_CLIENT_ID', 'test.apps.googleusercontent.com')
    monkeypatch.setenv('AUTH_PUBLIC_ORIGIN', 'http://localhost:3000')
    monkeypatch.setenv('SMTP_HOST', 'smtp.example.com')
    monkeypatch.setenv('SMTP_USERNAME', 'test-only-user')
    monkeypatch.setenv('SMTP_PASSWORD', 'test-only-smtp-password')
    monkeypatch.setenv('SMTP_FROM', 'support@example.com')
    get_settings.cache_clear()

def flow(client, mode='login'):
    result = client.post(GOOGLE+'/start', json={'mode': mode})
    assert result.status_code == 200, result.text
    return result.json()

def claims(monkeypatch, nonce, email='pedro@gmail.com', subject='google-subject-123', **extra):
    def verify(credential, request, audience):
        assert audience == 'test.apps.googleusercontent.com'
        assert credential == CREDENTIAL
        return {'sub': subject, 'email': email, 'email_verified': True, 'nonce': nonce, 'name': 'Pedro Google', **extra}
    monkeypatch.setattr(client_auth.id_token, 'verify_oauth2_token', verify)

def complete(client, state, **extra):
    return client.post(GOOGLE+'/complete', json={'state': state, 'credential': CREDENTIAL, **extra})

def test_google_registration_trial_and_login(client, database, monkeypatch):
    configure(monkeypatch)
    first = flow(client, 'register'); claims(monkeypatch, first['nonce'])
    response = complete(client, first['state'], company='Distribuidora Nova')
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['user']['role'] == 'admin' and data['company']['plan'] == 'trial'
    assert data['company']['trial_ends_at']-data['company']['trial_started_at'] == 604800
    assert CREDENTIAL not in response.text
    assert 'httponly' in response.headers['set-cookie'].lower()
    client.post('/api/v1/auth/logout')
    second = flow(client); claims(monkeypatch, second['nonce'])
    login = complete(client, second['state'])
    assert login.status_code == 200
    assert login.json()['company']['id'] == data['company']['id']
    with database() as db:
        assert len(db.scalars(select(Company)).all()) == 1
        assert db.get(GoogleIdentity, 'google-subject-123').user_id == data['user']['id']

def test_google_browser_nonce_replay_and_tenant_forgery(client, signup, monkeypatch):
    configure(monkeypatch)
    value = flow(client, 'register'); claims(monkeypatch, value['nonce'])
    assert complete(client, value['state'], company='Empresa', company_id='forged').status_code == 422
    browser_cookie = client.cookies.get('atendehub_google_flow')
    client.cookies.clear()
    assert complete(client, value['state'], company='Empresa').status_code == 409
    client.cookies.set('atendehub_google_flow', browser_cookie, path='/api/v1/auth/google')
    claims(monkeypatch, 'wrong-nonce')
    assert complete(client, value['state'], company='Empresa').status_code == 401
    claims(monkeypatch, value['nonce'])
    assert complete(client, value['state'], company='Empresa').status_code == 409

def test_google_authoritative_link_only_and_inactive_denied(client, database, signup, monkeypatch):
    configure(monkeypatch)
    original = client.post('/api/v1/auth/register', json={**signup, 'email': 'pedro@gmail.com'}).json()
    value = flow(client); claims(monkeypatch, value['nonce'])
    response = complete(client, value['state'])
    assert response.status_code == 200 and response.json()['company']['id'] == original['company']['id']
    with database() as db:
        user = db.get(User, original['user']['id']); user.active = False; db.commit()
    value = flow(client); claims(monkeypatch, value['nonce'])
    assert complete(client, value['state']).status_code == 401
    # A verified third-party email is NOT enough to merge an existing password account.
    client.post('/api/v1/auth/register', json={**signup, 'email': 'third@example.com'})
    value = flow(client); claims(monkeypatch, value['nonce'], email='third@example.com', subject='google-third')
    assert complete(client, value['state']).status_code == 409
    value = flow(client, 'register'); claims(monkeypatch, value['nonce'], email='third@example.com', subject='google-third')
    assert complete(client, value['state'], company='Duplicate').status_code == 409


def mail_setup(client, signup, monkeypatch):
    configure(monkeypatch)
    identity = client.post('/api/v1/auth/register', json=signup).json()
    sent = []
    monkeypatch.setattr(client_auth, 'send_reset_email', lambda settings, email, token: sent.append((email, token)))
    return identity, sent

def test_reset_single_use_hashed_tokens_revoke_sessions_and_no_enumeration(client, database, signup, monkeypatch):
    identity, sent = mail_setup(client, signup, monkeypatch)
    old_cookie = client.cookies.get('atendehub_session')
    known = client.post(PASSWORD+'/forgot', json={'email': signup['email']})
    unknown = client.post(PASSWORD+'/forgot', json={'email': 'unknown@example.com'})
    assert known.status_code == unknown.status_code == 202 and known.json() == unknown.json()
    token = sent[0][1]
    assert token not in known.text
    with database() as db:
        row = db.get(PasswordReset, digest(token)); assert row and not row.consumed
        assert row.user_id == identity['user']['id']
    assert client.post(PASSWORD+'/reset', json={'token': token, 'password': 'Nova-senha-123!', 'user_id': 'forged'}).status_code == 422
    assert client.post(PASSWORD+'/reset', json={'token': token, 'password': 'Nova-senha-123!'}).status_code == 200
    assert client.get('/api/v1/auth/me', headers={'Cookie': 'atendehub_session='+old_cookie}).status_code == 401
    assert client.post(PASSWORD+'/reset', json={'token': token, 'password': 'Outra-senha-123!'}).status_code == 400
    assert client.post('/api/v1/auth/login', json={'email': signup['email'], 'password': signup['password']}).status_code == 401
    assert client.post('/api/v1/auth/login', json={'email': signup['email'], 'password': 'Nova-senha-123!'}).status_code == 200

def test_reset_latest_link_expiry_and_concurrent_completion(client, database, signup, monkeypatch):
    identity, sent = mail_setup(client, signup, monkeypatch)
    client.post(PASSWORD+'/forgot', json={'email': signup['email']})
    client.post(PASSWORD+'/forgot', json={'email': signup['email']})
    assert client.post(PASSWORD+'/reset', json={'token': sent[0][1], 'password': 'Nova-senha-123!'}).status_code == 400
    token = sent[1][1]
    with ThreadPoolExecutor(max_workers=2) as workers:
        statuses = list(workers.map(lambda _: client.post(PASSWORD+'/reset', json={'token': token, 'password': 'Nova-senha-123!'}).status_code, range(2)))
    assert sorted(statuses) == [200, 400]
    client.post(PASSWORD+'/forgot', json={'email': signup['email']})
    token = sent[2][1]
    with database() as db:
        row = db.get(PasswordReset, digest(token)); row.expires_at = now()-1; db.commit()
    assert client.post(PASSWORD+'/reset', json={'token': token, 'password': 'Nova-senha-123!'}).status_code == 400


def test_missing_configuration_csrf_challenge_and_smtp_failure(client, signup, monkeypatch):
    assert client.get('/api/v1/auth/options').json()['google_enabled'] is False
    assert client.post(GOOGLE+'/start', json={'mode': 'login'}).status_code == 503
    assert client.post(PASSWORD+'/forgot', json={'email': signup['email']}).status_code == 503
    identity, sent = mail_setup(client, signup, monkeypatch)
    assert client.post(PASSWORD+'/forgot', json={'email': signup['email']}, headers={'Origin': 'https://evil.example'}).status_code == 403
    def failure(*args): raise RuntimeError('secret-not-to-return')
    monkeypatch.setattr(client_auth, 'send_reset_email', failure)
    failed = client.post(PASSWORD+'/forgot', json={'email': signup['email']})
    assert failed.status_code == 202 and 'secret-not-to-return' not in failed.text
    monkeypatch.setenv('TURNSTILE_ENABLED', 'true'); monkeypatch.setenv('TURNSTILE_SITE_KEY', 'site'); monkeypatch.setenv('TURNSTILE_SECRET_KEY', 'secret'); monkeypatch.setenv('TURNSTILE_ALLOWED_HOSTNAMES', '["localhost"]'); get_settings.cache_clear()
    assert client.post(PASSWORD+'/forgot', json={'email': signup['email']}).status_code == 403


@pytest.mark.parametrize('mode', ['valid','wrong-audience','expired','issuer','nonce','unverified'])
def test_google_real_signature_and_claim_validation(monkeypatch, mode):
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    from google.auth import jwt, crypt
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    payload = {'iss': 'https://accounts.google.com' if mode!='issuer' else 'https://evil.example', 'aud': 'client-id' if mode!='wrong-audience' else 'other-client', 'sub':'1234567890', 'email':'pedro@gmail.com', 'email_verified':mode!='unverified', 'iat':now()-400, 'exp':now()+300 if mode!='expired' else now()-300, 'nonce':'valid-nonce' if mode!='nonce' else 'wrong'}
    credential = jwt.encode(crypt.RSASigner.from_string(private, key_id='test-key'), payload).decode()
    class Transport:
        session = SimpleNamespace(close=lambda:None)
        def __call__(self, url, method='GET', **kwargs):
            assert url == 'https://www.googleapis.com/oauth2/v1/certs'
            return SimpleNamespace(status=200, data=json.dumps({'test-key':public}).encode())
    monkeypatch.setattr(client_auth, 'BoundedGoogleRequest', Transport)
    if mode == 'valid': assert client_auth.verify_google(credential,'client-id',digest('valid-nonce'))['subject'] == '1234567890'
    else:
        from fastapi import HTTPException
        with pytest.raises(HTTPException): client_auth.verify_google(credential,'client-id',digest('valid-nonce'))


def test_smtp_uses_starttls_and_private_fragment_link(monkeypatch):
    configure(monkeypatch)
    calls = []
    class SMTP:
        def __init__(self, host, port, timeout):
            assert (host, port, timeout) == ('smtp.example.com', 587, 8)
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def ehlo(self): calls.append('ehlo')
        def starttls(self, context): assert context.check_hostname; calls.append('tls')
        def login(self, user, password): assert calls == ['ehlo', 'tls', 'ehlo']; calls.append('login')
        def send_message(self, message):
            assert calls[-1] == 'login'
            assert message['To'] == 'pedro@example.com'
            assert '/redefinir-senha#token=test-only-reset-token' in message.get_content()
            assert '?token=' not in message.get_content()
            calls.append('sent')
    monkeypatch.setattr(client_auth.smtplib, 'SMTP', SMTP)
    client_auth.send_reset_email(get_settings(), 'pedro@example.com', 'test-only-reset-token')
    assert calls[-1] == 'sent'


def test_inflight_old_password_cannot_issue_session_after_reset(client, database, signup, monkeypatch):
    from app.services import auth
    from app.core.security import passwords
    client.post('/api/v1/auth/register', json=signup)
    real_verify = auth.verify_password
    def verify_then_password_changed(password, encoded):
        valid = real_verify(password, encoded)
        with database() as db:
            user = db.scalar(select(User)); user.password_hash = passwords.hash('Changed-during-login-123!'); db.commit()
        return valid
    monkeypatch.setattr(auth, 'verify_password', verify_then_password_changed)
    response = client.post('/api/v1/auth/login', json={'email':signup['email'], 'password':signup['password']})
    assert response.status_code == 401
