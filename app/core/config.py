from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator, Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    app_env: Literal['development', 'test', 'production'] = 'development'
    database_url: str = 'sqlite:///./data/atendehub.db'
    allowed_origins: list[str] = ['http://localhost:3000', 'http://127.0.0.1:3000']
    cookie_secure: bool = False
    session_hours: int = Field(default=12, ge=1, le=168)
    remember_days: int = Field(default=7, ge=1, le=30)

    @model_validator(mode='after')
    def production_checks(self):
        if self.app_env == 'production':
            if not self.cookie_secure or not self.allowed_origins or any(not o.startswith('https://') for o in self.allowed_origins):
                raise ValueError('Production requires secure cookies and explicit HTTPS origins')
            if self.database_url.startswith('sqlite'):
                raise ValueError('SQLite is development-only; validate PostgreSQL before production')
        return self

@lru_cache
def get_settings():
    return Settings()

COOKIE_NAME = 'atendehub_session'
