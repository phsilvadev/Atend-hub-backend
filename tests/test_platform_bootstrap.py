import pytest
from sqlalchemy import select, func
from app.cli.platform_bootstrap import provision, EMAIL_VARIABLE, PASSWORD_VARIABLE
from app.models.knowledge import PlatformAdmin, PlatformAudit
from app.models.auth import Company
from app.core.security import passwords


def test_bootstrap_creates_real_admin_without_tenant_and_is_idempotent(database):
    environment={EMAIL_VARIABLE:'OWNER@example.com',PASSWORD_VARIABLE:'unit-test-only-bootstrap-password-123'}
    with database() as db:
        assert provision(db,environment)=='CREATED'
        admin=db.scalar(select(PlatformAdmin))
        assert admin.email=='owner@example.com' and admin.active
        assert passwords.verify(environment[PASSWORD_VARIABLE],admin.password_hash)
        original_hash=admin.password_hash
        assert provision(db,{**environment,PASSWORD_VARIABLE:'different-unit-password-999'})=='ALREADY_EXISTS'
        db.refresh(admin)
        assert admin.password_hash==original_hash
        assert db.scalar(select(func.count()).select_from(PlatformAdmin))==1
        assert db.scalar(select(func.count()).select_from(PlatformAudit))==1
        assert db.scalar(select(func.count()).select_from(Company))==0


def test_bootstrap_skips_without_variables_and_rejects_partial_configuration(database):
    with database() as db:
        assert provision(db,{})=='NOT_REQUESTED'
        with pytest.raises(ValueError):provision(db,{EMAIL_VARIABLE:'owner@example.com'})
        assert db.scalar(select(func.count()).select_from(PlatformAdmin))==0


def test_bootstrap_never_reactivates_existing_admin(database):
    env={EMAIL_VARIABLE:'owner@example.com',PASSWORD_VARIABLE:'unit-test-only-bootstrap-password-123'}
    with database() as db:
        assert provision(db,env)=='CREATED'
        admin=db.scalar(select(PlatformAdmin));admin.active=False;db.commit()
        assert provision(db,env)=='ALREADY_EXISTS'
        db.refresh(admin);assert not admin.active
