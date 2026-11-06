import json
from types import SimpleNamespace
from pydantic import SecretStr
from sqlalchemy import text
from app.core.database import make_engine
from app.integrations.firebase import product_images as firebase


def test_railway_postgresql_urls_use_psycopg_without_opening_connection():
    for url in ['postgresql://unit:unit-password@localhost:5432/test', 'postgres://unit:unit-password@localhost:5432/test', 'postgresql+psycopg://unit:unit-password@localhost:5432/test']:
        engine = make_engine(url)
        assert engine.dialect.name == 'postgresql' and engine.dialect.driver == 'psycopg'
        assert engine.pool._pre_ping is True
        engine.dispose()


def test_readiness_requires_current_migrations(client, database):
    assert client.get('/health').json() == {'status':'ok'}
    assert client.get('/health/ready').json() == {'status':'ready'}
    with database() as db:
        db.execute(text("UPDATE alembic_version SET version_num = 'outdated-for-test'")); db.commit()
    result=client.get('/health/ready')
    assert result.status_code == 503 and result.json() == {'status':'not_ready'}
    assert 'outdated-for-test' not in result.text


def test_firebase_uses_secret_json_without_exposing_it(monkeypatch):
    fake={'type':'service_account','project_id':'unit-test-project','private_key':'unit-test-not-real-key'}
    settings=SimpleNamespace(google_application_credentials='',google_service_account_json=SecretStr(json.dumps(fake)))
    monkeypatch.setattr(firebase,'get_settings',lambda:settings)
    received=[]
    credential,app,bucket=object(),object(),object()
    def certificate(value):received.append(value);return credential
    monkeypatch.setattr(firebase.credentials,'Certificate',certificate)
    monkeypatch.setattr(firebase.firebase_admin,'initialize_app',lambda *args,**kwargs:app)
    monkeypatch.setattr(firebase.storage,'bucket',lambda **kwargs:bucket)
    firebase._bucket.cache_clear()
    try:
        assert firebase._bucket('unit-test.firebasestorage.app') is bucket
        assert received == [fake]
        assert fake['private_key'] not in str(settings.google_service_account_json)
    finally:firebase._bucket.cache_clear()
