import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app.core.config import get_settings
from app.core.database import get_db, make_engine
from app.main import app

@pytest.fixture
def database(tmp_path, monkeypatch):
    url = f'sqlite:///{tmp_path}/test.db'
    monkeypatch.setenv('DATABASE_URL', url)
    monkeypatch.setenv('APP_ENV', 'development')
    get_settings.cache_clear()
    command.upgrade(Config('alembic.ini'), 'head')
    engine = make_engine(url)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    def override_db():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    yield factory
    app.dependency_overrides.clear()
    engine.dispose()
    get_settings.cache_clear()

@pytest.fixture
def client(database):
    with TestClient(app, headers={'Origin': 'http://localhost:3000'}) as client:
        yield client

@pytest.fixture
def signup():
    return {'name':'Pedro Almeida', 'company':'Distribuidora Alfa', 'email':'pedro@example.com', 'password':'Senha-teste-123'}
