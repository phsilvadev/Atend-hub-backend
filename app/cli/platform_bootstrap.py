"""Optional initial admin provisioning from private deployment variables. No public API."""
import os
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from pydantic import TypeAdapter, EmailStr
from app.core.database import SessionLocal
from app.models.knowledge import PlatformAdmin
from app.services.platform_auth import bootstrap

EMAIL_VARIABLE = 'PLATFORM_ADMIN_BOOTSTRAP_EMAIL'
PASSWORD_VARIABLE = 'PLATFORM_ADMIN_BOOTSTRAP_PASSWORD'

def provision(db, environment):
    email = environment.get(EMAIL_VARIABLE, '')
    password = environment.get(PASSWORD_VARIABLE, '')
    if not email and not password:
        return 'NOT_REQUESTED'
    if not email or not password:
        raise ValueError('Configure as duas variáveis privadas para o provisionamento inicial.')
    email = str(TypeAdapter(EmailStr).validate_python(email.strip().lower()))
    if db.scalar(select(PlatformAdmin).where(PlatformAdmin.email == email)):
        return 'ALREADY_EXISTS'  # Never activate/reset/modify an existing administrator.
    try:
        bootstrap(db, 'Administrador da plataforma', email, password)
    except IntegrityError:
        db.rollback()
        if db.scalar(select(PlatformAdmin).where(PlatformAdmin.email == email)):
            return 'ALREADY_EXISTS'
        raise
    return 'CREATED'

def main():
    try:
        with SessionLocal() as db:
            status = provision(db, os.environ)
    except Exception:
        # Do not log passwords, environment values, email validation input or DB URLs.
        raise SystemExit('INITIAL_PLATFORM_ADMIN_FAILED: revise a configuração protegida.') from None
    print('INITIAL_PLATFORM_ADMIN_' + status)

if __name__ == '__main__':
    main()
