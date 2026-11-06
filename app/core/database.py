from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.config import get_settings

class Base(DeclarativeBase):
    pass

def make_engine(url):
    parsed = make_url(url)
    if parsed.drivername in ('postgres', 'postgresql'):
        url = parsed.set(drivername='postgresql+psycopg')
    if isinstance(url, str) and url.startswith('sqlite:///') and ':memory:' not in url:
        Path(url.removeprefix('sqlite:///')).parent.mkdir(parents=True, exist_ok=True)
    sqlite = make_url(url).get_backend_name() == 'sqlite'
    engine = create_engine(url, connect_args={'check_same_thread': False, 'timeout': 15} if sqlite else {'connect_timeout': 10}, pool_pre_ping=not sqlite)
    if sqlite:
        @event.listens_for(engine, 'connect')
        def configure_connection(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute('PRAGMA busy_timeout=15000')
    return engine

engine = make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def get_db():
    with SessionLocal() as db:
        yield db
