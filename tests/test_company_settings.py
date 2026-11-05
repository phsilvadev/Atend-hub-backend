import pytest
from sqlalchemy import select
from tests.test_auth import register
from app.core.config import COOKIE_NAME
from app.core.security import now
from app.models.auth import Company, CompanyProfile, AuditEvent


def test_company_defaults_save_isolation_audit(client, signup, database):
    alfa = register(client, signup)
    token = client.cookies.get(COOKIE_NAME)
    url = '/api/v1/company/settings'
    before = client.get(url).json()
    assert before['company_id'] == alfa['company']['id'] and before['name'] == signup['company']
    assert before['legal_name'] == '' and len(before['business_hours']) == 7
    assert not any(day['enabled'] for day in before['business_hours'].values())
    data = {key: value for key, value in before.items() if key != 'company_id'}
    data.update(name='Alfa Aços', legal_name='Alfa Comércio Ltda', tax_id='11.222.333/0001-81', phone='(11) 3333-4444', email=' COMERCIAL@example.com ', postal_code='01001-000', street='Praça da Sé', city='São Paulo', state='sp')
    data['business_hours']['mon'] = {'enabled': True, 'opens': '08:00', 'closes': '18:00'}
    result = client.patch(url, json=data)
    assert result.status_code == 200, result.text
    body = result.json()
    assert body['tax_id'] == '11222333000181' and body['postal_code'] == '01001000'
    assert body['phone'] == '1133334444' and body['state'] == 'SP'
    assert client.get('/api/v1/auth/me').json()['company']['name'] == 'Alfa Aços'
    with database() as db:
        assert db.get(CompanyProfile, alfa['company']['id']).email == 'comercial@example.com'
        assert db.scalar(select(AuditEvent).where(AuditEvent.action == 'company.settings.updated')).company_id == alfa['company']['id']
    beta = register(client, {**signup, 'company': 'Beta', 'email': 'beta@example.com'})
    assert client.get(url).json()['legal_name'] == ''
    assert client.patch(url, json={**data, 'company_id': alfa['company']['id']}).status_code == 422
    assert client.patch(url, json={**data, 'plan': 'paid'}).status_code == 422
    assert client.patch(url, json={**data, 'name': 'Beta Atualizada'}).status_code == 200
    client.cookies.clear(); client.cookies.set(COOKIE_NAME, token)
    assert client.get(url).json() == body
    assert client.get(f"/api/v1/company/{beta['company']['id']}/settings").status_code == 404


@pytest.mark.parametrize('bad', [
    {'name': '  '}, {'tax_id':'11111111111111'}, {'tax_id':'11222333000182'},
    {'email':'invalido'}, {'phone':'abc123'}, {'postal_code':'012'}, {'state':'ZZ'},
    {'timezone':'Fake/Zone'}, {'business_hours': {}},
    {'business_hours': {day: {'enabled': True, 'opens':'18:00', 'closes':'08:00'} for day in ['mon','tue','wed','thu','fri','sat','sun']}},
    {'business_hours': {day: {'enabled': True, 'opens':'25:00', 'closes':'26:00'} for day in ['mon','tue','wed','thu','fri','sat','sun']}},
])
def test_company_validation_atomic(client, signup, bad):
    register(client, signup)
    before = client.get('/api/v1/company/settings').json()
    data = {key: value for key,value in before.items() if key != 'company_id'}
    assert client.patch('/api/v1/company/settings', json={**data, **bad}).status_code == 422
    assert client.get('/api/v1/company/settings').json() == before


def test_company_permissions_trial_csrf(client, signup, database):
    identity = register(client, signup)
    token = client.cookies.get(COOKIE_NAME)
    url = '/api/v1/company/settings'
    data = client.get(url).json(); data.pop('company_id')
    seller = {'name':'Vendedor', 'email':'seller@example.com', 'password':'Senha-teste-123', 'role':'seller'}
    client.post('/api/v1/users', json=seller)
    client.post('/api/v1/auth/login', json={'email':seller['email'], 'password':seller['password']})
    assert client.get(url).status_code == 200
    assert client.patch(url, json={**data,'name':'Proibido'}).status_code == 403
    client.cookies.clear(); client.cookies.set(COOKIE_NAME, token)
    assert client.patch(url, json=data, headers={'Origin':'https://evil.example'}).status_code == 403
    with database() as db:
        db.get(Company, identity['company']['id']).trial_ends_at = now()
        db.commit()
    assert client.get(url).status_code == 403
    assert client.patch(url, json=data).status_code == 403
    client.cookies.clear()
    assert client.get(url).status_code == 401
    assert client.patch(url, json=data).status_code == 401


def test_profile_migration_preserves_existing_company(client, signup, database):
    from alembic import command
    from alembic.config import Config
    identity = register(client, signup)
    command.downgrade(Config('alembic.ini'), '9c1654c4b7c0')
    command.upgrade(Config('alembic.ini'), 'head')
    assert client.get('/api/v1/auth/me').json()['company']['id'] == identity['company']['id']
    result = client.get('/api/v1/company/settings')
    assert result.status_code == 200 and result.json()['name'] == signup['company']
