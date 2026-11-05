from tests.test_auth import register
from app.core.config import COOKIE_NAME
from app.models.auth import AuditEvent
from sqlalchemy import select


def test_edit_scoped_validated_audited(client, signup, database):
    first = register(client, signup)
    token = client.cookies.get(COOKIE_NAME)
    second = register(client, {**signup, 'email': 'beta@example.com', 'company': 'Beta'})
    data = {'name': 'Novo Nome', 'email': 'novo@example.com', 'role': 'seller', 'active': True}
    url = f"/api/v1/users/{first['user']['id']}"
    assert client.patch(url, json=data).status_code == 404
    client.cookies.clear()
    client.cookies.set(COOKIE_NAME, token)
    for field in ({'company_id': second['company']['id']}, {'password': 'secret'}, {'role': 'root'}):
        assert client.patch(url, json={**data, **field}).status_code == 422
    assert client.patch(url, json=data).status_code == 409  # cannot demote self
    assert client.patch(url, json={**data, 'role': 'admin', 'active': False}).status_code == 409
    result = client.patch(url, json={**data, 'role': 'admin', 'email': signup['email']})
    assert result.status_code == 200 and result.json()['name'] == 'Novo Nome'
    with database() as db:
        assert db.scalar(select(AuditEvent).where(AuditEvent.action == 'user.updated'))


def test_edit_duplicate_and_revoke_permissions(client, signup):
    admin = register(client, signup)
    token = client.cookies.get(COOKIE_NAME)
    worker = {'name': 'Vendedor', 'email': 'seller@example.com', 'password': 'Senha-teste-123', 'role': 'seller'}
    user = client.post('/api/v1/users', json=worker).json()
    url = f"/api/v1/users/{user['id']}"
    update = {'name': 'Nome Atualizado', 'email': worker['email'], 'role': 'operator', 'active': True}
    assert client.patch(url, json={**update, 'email': signup['email']}).status_code == 409
    assert client.get(url).json()['name'] == worker['name']
    client.post('/api/v1/auth/login', json={'email': worker['email'], 'password': worker['password']})
    seller_token = client.cookies.get(COOKIE_NAME)
    assert client.patch(url, json=update).status_code == 403
    client.cookies.clear(); client.cookies.set(COOKIE_NAME, token)
    result = client.patch(url, json=update)
    assert result.status_code == 200 and result.json()['role'] == 'operator'
    client.cookies.clear(); client.cookies.set(COOKIE_NAME, seller_token)
    assert client.get('/api/v1/auth/me').status_code == 401
    client.cookies.clear(); client.cookies.set(COOKIE_NAME, token)
    assert client.patch(url, json={**update, 'active': False}).status_code == 200
    assert client.post('/api/v1/auth/login', json={'email': worker['email'], 'password': worker['password']}).status_code == 401
    assert client.patch(f"/api/v1/users/{admin['user']['id']}", json=update, headers={'Origin': 'https://evil.example'}).status_code == 403
