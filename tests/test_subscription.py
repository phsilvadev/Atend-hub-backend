from tests.test_auth import register
from app.core.config import COOKIE_NAME
from app.core.security import now
from app.models.auth import Company


def test_subscription_real_trial_count_and_tenant(client, signup, database):
    alfa = register(client, signup)
    token = client.cookies.get(COOKIE_NAME)
    url = '/api/v1/company/subscription'
    body = client.get(url).json()
    assert body['company_id'] == alfa['company']['id']
    assert body['trial_days_remaining'] == 7 and body['status'] == 'trial_active'
    assert body['total_users'] == body['active_users'] == 1
    assert not body['billing_enabled']
    client.post('/api/v1/users', json={'name':'Vendedor','email':'seller@example.com','password':'Senha-teste-123','role':'seller'})
    assert client.get(url).json()['total_users'] == 2
    client.post('/api/v1/auth/login', json={'email':'seller@example.com','password':'Senha-teste-123'})
    assert client.get(url).status_code == 200
    assert client.patch(url, json={'plan_code':'enterprise'}).status_code == 405
    register(client, {**signup, 'company':'Beta', 'email':'beta@example.com'})
    assert client.get(url).json()['total_users'] == 1
    client.cookies.clear(); client.cookies.set(COOKIE_NAME, token)
    with database() as db:
        db.get(Company, alfa['company']['id']).trial_ends_at = now() - 1
        db.commit()
    expired = client.get(url).json()
    assert expired['status'] == 'trial_expired' and expired['trial_days_remaining'] == 0
    assert client.get('/api/v1/users').status_code == 403
    with database() as db:
        db.get(Company, alfa['company']['id']).plan = 'professional'
        db.commit()
    paid = client.get(url).json()
    assert paid['status'] == 'active' and paid['trial_ends_at'] is None and paid['trial_days_remaining'] is None
    client.cookies.clear()
    assert client.get(url).status_code == 401


def test_plan_catalog_seed_idempotent_db_changes_and_production(client, signup, database, monkeypatch):
    from types import SimpleNamespace
    from app.seeds.plans import seed_plans
    from app.models.auth import Plan
    from app.api import routes
    import pytest
    register(client, signup)
    url = '/api/v1/company/subscription'
    assert client.get(url).json()['available_plans'] == []
    with database() as db:
        assert seed_plans(db, SimpleNamespace(app_env='test')) == 3
        assert seed_plans(db, SimpleNamespace(app_env='test')) == 0
        db.get(Plan, 'essential').monthly_price_cents = 19950
        db.get(Plan, 'essential').name = 'Nome definido no banco'
        from sqlalchemy import select
        db.scalar(select(Company)).plan = 'essential'
        db.get(Plan, 'enterprise').active = False
        db.commit()
        with pytest.raises(RuntimeError):
            seed_plans(db, SimpleNamespace(app_env='production'))
    plans = client.get(url).json()['available_plans']
    assert len(plans) == 2 and plans[0]['monthly_price_cents'] == 19950
    assert plans[0]['user_limit'] == 3 and plans[0]['is_demo']
    current = client.get(url).json()
    assert current['plan_name'] == 'Nome definido no banco'
    assert current['current_plan']['monthly_price_cents'] == 19950
    assert current['status'] == 'active'
    monkeypatch.setattr(routes, 'get_settings', lambda: SimpleNamespace(app_env='production'))
    assert client.get(url).json()['available_plans'] == []
