from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from app.core.database import make_engine
from app.core.config import get_settings

def test_upgrade_downgrade_upgrade(tmp_path, monkeypatch):
    url=f'sqlite:///{tmp_path}/migrations.db'
    monkeypatch.setenv('DATABASE_URL',url)
    get_settings.cache_clear()
    config=Config('alembic.ini')
    command.upgrade(config,'head')
    engine=make_engine(url)
    assert {'companies','users','sessions','audit_events','auth_attempts'} <= set(inspect(engine).get_table_names())
    command.check(config)
    command.downgrade(config,'base')
    assert 'users' not in inspect(engine).get_table_names()
    command.upgrade(config,'head')
    assert 'users' in inspect(engine).get_table_names()
    engine.dispose()
    get_settings.cache_clear()
