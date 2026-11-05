from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator, Field, SecretStr
from urllib.parse import urlsplit

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    app_env: Literal['development', 'test', 'production'] = 'development'
    database_url: str = 'sqlite:///./data/atendehub.db'
    allowed_origins: list[str] = ['http://localhost:3000', 'http://127.0.0.1:3000', 'http://localhost:3001', 'http://127.0.0.1:3001']
    whatsapp_app_secret: SecretStr = SecretStr('')
    whatsapp_verify_token: SecretStr = SecretStr('')
    whatsapp_qr_bridge_url: str = ''
    whatsapp_qr_bridge_token: SecretStr = SecretStr('')
    whatsapp_app_id: str = Field(default='',pattern=r'^\d{0,40}$')
    whatsapp_credential_key: SecretStr = SecretStr('')
    whatsapp_graph_version: str = Field(default='v25.0',pattern=r'^v[0-9]{1,3}\.0$')
    whatsapp_public_webhook_url: str = ''
    cookie_secure: bool = False
    session_hours: int = Field(default=12, ge=1, le=168)
    remember_days: int = Field(default=7, ge=1, le=30)

    @model_validator(mode='after')
    def production_checks(self):
        if self.whatsapp_public_webhook_url:
            parsed=urlsplit(self.whatsapp_public_webhook_url)
            if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path!='/api/v1/webhooks/whatsapp':
                raise ValueError('Public webhook must use HTTPS and the official webhook path')
        if self.whatsapp_qr_bridge_url:
            parsed=urlsplit(self.whatsapp_qr_bridge_url)
            if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/') or not parsed.hostname or (parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in ('localhost','127.0.0.1','::1'))):
                raise ValueError('QR gateway requires HTTPS or localhost HTTP, without credentials or path')
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
