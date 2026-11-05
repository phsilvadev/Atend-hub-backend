import uuid
from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

def uid():
    return str(uuid.uuid4())

class Company(Base):
    __tablename__ = 'companies'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(160))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    plan: Mapped[str] = mapped_column(String(20), default='trial')
    trial_started_at: Mapped[int] = mapped_column(Integer)
    trial_ends_at: Mapped[int] = mapped_column(Integer)

class User(Base):
    __tablename__ = 'users'
    __table_args__ = (UniqueConstraint('id', 'company_id', name='uq_user_company'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str] = mapped_column(ForeignKey('companies.id'), index=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    role: Mapped[str] = mapped_column(String(20), default='admin')
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class Session(Base):
    __tablename__ = 'sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    company_id: Mapped[str] = mapped_column(ForeignKey('companies.id'), index=True)
    expires_at: Mapped[int] = mapped_column(Integer, index=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)

class AuditEvent(Base):
    __tablename__ = 'audit_events'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str] = mapped_column(ForeignKey('companies.id'), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[int] = mapped_column(Integer)

class AuthAttempt(Base):
    __tablename__ = 'auth_attempts'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    key_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[int] = mapped_column(Integer, index=True)

class CompanyProfile(Base):
    __tablename__ = 'company_profiles'
    company_id: Mapped[str] = mapped_column(ForeignKey('companies.id'), primary_key=True)
    legal_name: Mapped[str] = mapped_column(String(160), default='')
    tax_id: Mapped[str] = mapped_column(String(14), default='')
    phone: Mapped[str] = mapped_column(String(20), default='')
    email: Mapped[str] = mapped_column(String(254), default='')
    postal_code: Mapped[str] = mapped_column(String(8), default='')
    street: Mapped[str] = mapped_column(String(160), default='')
    number: Mapped[str] = mapped_column(String(20), default='')
    complement: Mapped[str] = mapped_column(String(100), default='')
    district: Mapped[str] = mapped_column(String(100), default='')
    city: Mapped[str] = mapped_column(String(100), default='')
    state: Mapped[str] = mapped_column(String(2), default='')
    timezone: Mapped[str] = mapped_column(String(64), default='America/Sao_Paulo')
    business_hours: Mapped[dict] = mapped_column(JSON, default=dict)
