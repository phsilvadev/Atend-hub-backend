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
    whatsapp_embedded_config_id: str = Field(default='',pattern=r'^\d{0,40}$')
    whatsapp_app_id: str = Field(default='',pattern=r'^\d{0,40}$')
    whatsapp_credential_key: SecretStr = SecretStr('')
    whatsapp_graph_version: str = Field(default='v25.0',pattern=r'^v[0-9]{1,3}\.0$')
    whatsapp_public_webhook_url: str = ''
    google_application_credentials: str = ''
    google_service_account_json: SecretStr = SecretStr('')
    firebase_storage_bucket: str = Field(default="", pattern=r"^[a-z0-9][a-z0-9._-]{1,220}[a-z0-9]$|^$")
    turnstile_enabled: bool = False
    turnstile_site_key: str = ''
    turnstile_secret_key: SecretStr = SecretStr('')
    turnstile_allowed_hostnames: list[str] = []
    turnstile_testing: bool = False
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
        if self.turnstile_enabled:
            if not self.turnstile_site_key or not self.turnstile_secret_key.get_secret_value():
                raise ValueError('Turnstile requires site and secret keys')
            if not self.turnstile_testing and not self.turnstile_allowed_hostnames:
                raise ValueError('Turnstile requires an explicit hostname allowlist')
            if any(not host or '/' in host or ':' in host or '*' in host or host != host.lower() for host in self.turnstile_allowed_hostnames):
                raise ValueError('Use exact lowercase Turnstile hostnames, without scheme, wildcard or port')
        if self.app_env == 'production':
            if not self.turnstile_enabled or self.turnstile_testing or self.turnstile_site_key.startswith(('1x000000', '2x000000', '3x000000')) or self.turnstile_secret_key.get_secret_value().startswith(('1x000000', '2x000000', '3x000000')):
                raise ValueError('Production requires Turnstile with real credentials and an explicit hostname allowlist')
            if not self.cookie_secure or not self.allowed_origins or any(not o.startswith('https://') for o in self.allowed_origins):
                raise ValueError('Production requires secure cookies and explicit HTTPS origins')
            if self.database_url.startswith('sqlite'):
                raise ValueError('SQLite is development-only; validate PostgreSQL before production')
        return self

@lru_cache
def get_settings():
    return Settings()

COOKIE_NAME = 'atendehub_session'
