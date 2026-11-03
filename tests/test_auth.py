import pytest
from sqlalchemy import select, func
from app.models.auth import User, Company, Session, AuditEvent
from app.core.config import COOKIE_NAME, Settings
from app.core.security import passwords, digest, now

def register(client, data):
    response = client.post('/api/v1/auth/register', json=data)
    assert response.status_code == 201, response.text
    return response.json()

def test_registration_trial_hash_audit(client, database, signup):
    result = register(client, signup)
    assert result['company']['plan'] == 'trial'
    assert result['company']['trial_ends_at'] - result['company']['trial_started_at'] == 7 * 86400
    assert abs(result['company']['trial_started_at'] - now()) < 5
    assert result['user']['role'] == 'admin' and not result['trial_expired']
    assert 'password' not in str(result)
    me = client.get('/api/v1/auth/me')
    assert me.status_code == 200 and me.headers['cache-control'] == 'no-store'
    raw_token = client.cookies.get(COOKIE_NAME)
    with database() as db:
        user = db.get(User, result['user']['id'])
        assert user.password_hash.startswith('$argon2')
        assert passwords.verify(signup['password'], user.password_hash)
        session = db.get(Session, digest(raw_token))
        assert session.company_id == user.company_id and session.token_hash != raw_token
        assert db.scalar(select(func.count()).select_from(AuditEvent)) == 1

def test_cookie_remember_login(client, signup):
    response = client.post('/api/v1/auth/register', json=signup)
    cookie = response.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=lax' in cookie and 'path=/' in cookie
    assert 'max-age' not in cookie
    assert client.post('/api/v1/auth/logout').status_code == 204
    response = client.post('/api/v1/auth/login', json={'email':signup['email'],'password':signup['password'],'remember':True})
    assert response.status_code == 200 and 'Max-Age=604800' in response.headers['set-cookie']

def test_duplicate_rolls_back_company(client, database, signup):
    register(client, signup)
    assert client.post('/api/v1/auth/register', json={**signup,'email':'PEDRO@example.com'}).status_code == 409
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Company)) == 1
        assert db.scalar(select(func.count()).select_from(User)) == 1

@pytest.mark.parametrize('extra',[{'company_id':'forged'},{'role':'admin'},{'trial_ends_at':9999999999},{'plan':'paid'}])
def test_cannot_override_tenant_plan_role(client, signup, extra):
    assert client.post('/api/v1/auth/register',json={**signup,**extra}).status_code == 422
    assert client.get('/api/v1/auth/me').status_code == 401

def test_generic_error_no_password_echo(client, signup):
    register(client, signup)
    existing=client.post('/api/v1/auth/login',json={'email':signup['email'],'password':'wrong'})
    missing=client.post('/api/v1/auth/login',json={'email':'unknown@example.com','password':'wrong'})
    assert existing.status_code == missing.status_code == 401
    assert existing.json() == missing.json()
    response=client.post('/api/v1/auth/register',json={**signup,'password':'secret'})
    assert response.status_code == 422 and 'secret' not in response.text

def test_logout_revoke_replay(client, signup):
    register(client, signup)
    token=client.cookies.get(COOKIE_NAME)
    assert client.post('/api/v1/auth/logout').status_code == 204
    assert client.get('/api/v1/auth/me').status_code == 401
    client.cookies.set(COOKIE_NAME,token)
    assert client.get('/api/v1/auth/me').status_code == 401
    assert client.get('/api/v1/users').status_code == 401

def test_expired_session_forgery(client, database, signup):
    register(client, signup)
    with database() as db:
        db.get(Session,digest(client.cookies.get(COOKIE_NAME))).expires_at=now()
        db.commit()
    assert client.get('/api/v1/auth/me').status_code == 401
    client.cookies.clear()
    client.cookies.set(COOKIE_NAME,'forged')
    assert client.get('/api/v1/users').status_code == 401

@pytest.mark.parametrize('entity',['user','company'])
def test_inactive_loses_access(client, database, signup, entity):
    result=register(client, signup)
    with database() as db:
        db.get(User if entity=='user' else Company,result[entity]['id']).active=False
        db.commit()
    assert client.get('/api/v1/auth/me').status_code == 401
    assert client.post('/api/v1/auth/login',json={k:signup[k] for k in ('email','password')}).status_code == 401

def test_tenant_isolation_permissions(client, signup):
    alfa=register(client, signup)
    alfa_token=client.cookies.get(COOKIE_NAME)
    beta=register(client,{**signup,'company':'Distribuidora Beta','email':'beta@example.com'})
    assert client.get(f"/api/v1/users/{alfa['user']['id']}").status_code == 404
    assert [u['id'] for u in client.get('/api/v1/users').json()] == [beta['user']['id']]
    data={'name':'Vendedor','email':'seller@example.com','password':'Senha-teste-123','role':'seller'}
    assert client.post('/api/v1/users',json={**data,'company_id':alfa['company']['id']}).status_code == 422
    response=client.post('/api/v1/users',json=data)
    assert response.status_code == 201 and response.json()['company_id'] == beta['company']['id']
    assert 'password_hash' not in response.text
    client.post('/api/v1/auth/logout')
    client.post('/api/v1/auth/login',json={'email':data['email'],'password':data['password']})
    assert client.get('/api/v1/users').status_code == 403
    assert client.post('/api/v1/users',json={**data,'email':'admin@example.com','role':'admin'}).status_code == 403
    client.cookies.clear()
    client.cookies.set(COOKIE_NAME,alfa_token)
    assert client.get(f"/api/v1/users/{beta['user']['id']}").status_code == 404

def test_expired_trial_block_not_logout(client, database, signup):
    result=register(client,signup)
    with database() as db:
        db.get(Company,result['company']['id']).trial_ends_at=now()
        db.commit()
    me=client.get('/api/v1/auth/me')
    assert me.status_code == 200 and me.json()['trial_expired']
    response=client.get('/api/v1/users')
    assert response.status_code == 403 and response.json()['detail']['code']=='trial_expired'
    client.post('/api/v1/auth/logout')
    response=client.post('/api/v1/auth/login',json={k:signup[k] for k in ('email','password')})
    assert response.status_code == 200 and response.json()['trial_expired']
    assert client.post('/api/v1/auth/logout').status_code == 204

@pytest.mark.parametrize('origin',['https://evil.example','null',''])
def test_csrf(client, signup, origin):
    assert client.post('/api/v1/auth/register',json=signup,headers={'Origin':origin}).status_code == 403

def test_rate_limit(client):
    data={'email':'unknown@example.com','password':'wrong'}
    for _ in range(10):
        assert client.post('/api/v1/auth/login',json=data).status_code == 401
    response=client.post('/api/v1/auth/login',json=data)
    assert response.status_code == 429 and response.headers['retry-after']=='900'

def test_production_checks():
    with pytest.raises(ValueError):
        Settings(app_env='production',cookie_secure=False)
    with pytest.raises(ValueError):
        Settings(app_env='production',cookie_secure=True,allowed_origins=['https://app.example.com'])
