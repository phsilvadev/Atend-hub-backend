from sqlalchemy import String, Integer, Text, Boolean, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.models.auth import uid

class PlatformAdmin(Base):
    __tablename__ = 'platform_admins'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

class PlatformSession(Base):
    __tablename__ = 'platform_sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    admin_id: Mapped[str] = mapped_column(ForeignKey('platform_admins.id'), index=True)
    expires_at: Mapped[int] = mapped_column(Integer)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)

class PlatformAudit(Base):
    __tablename__ = 'platform_audit'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    admin_id: Mapped[str] = mapped_column(ForeignKey('platform_admins.id'))
    action: Mapped[str] = mapped_column(String(80))
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[int] = mapped_column(Integer)

class KnowledgeImport(Base):
    __tablename__ = 'knowledge_imports'
    __table_args__ = (UniqueConstraint('admin_id','request_id',name='uq_knowledge_import_request'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    admin_id: Mapped[str] = mapped_column(ForeignKey('platform_admins.id'))
    request_id: Mapped[str] = mapped_column(String(36))
    request_hash: Mapped[str] = mapped_column(String(64))
    authorization_reference: Mapped[str] = mapped_column(String(500))
    sanitized_messages: Mapped[list] = mapped_column(JSON)
    redactions: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[int] = mapped_column(Integer)

class KnowledgeEntry(Base):
    __tablename__ = 'knowledge_entries'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    import_id: Mapped[str | None] = mapped_column(ForeignKey('knowledge_imports.id'), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    current_revision: Mapped[int] = mapped_column(Integer, default=1)
    published_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[int] = mapped_column(Integer)

class KnowledgeRevision(Base):
    __tablename__ = 'knowledge_revisions'
    entry_id: Mapped[str] = mapped_column(ForeignKey('knowledge_entries.id'), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(180))
    body: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(30))
    source_reference: Mapped[str] = mapped_column(String(1000))
    category: Mapped[str] = mapped_column(String(80))
    admin_id: Mapped[str] = mapped_column(ForeignKey('platform_admins.id'))
    created_at: Mapped[int] = mapped_column(Integer)

class KnowledgeApproval(Base):
    __tablename__ = 'knowledge_approvals'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    entry_id: Mapped[str] = mapped_column(ForeignKey('knowledge_entries.id'))
    revision: Mapped[int] = mapped_column(Integer)
    admin_id: Mapped[str] = mapped_column(ForeignKey('platform_admins.id'))
    review_note: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[int] = mapped_column(Integer)

class PlatformControl(Base):
    __tablename__ = 'platform_control'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    primary_admin_id: Mapped[str | None] = mapped_column(ForeignKey('platform_admins.id'), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

class PlatformOpenAI(Base):
    __tablename__ = 'platform_openai'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(String(120), default='gpt-4.1-mini')
    version: Mapped[int] = mapped_column(Integer, default=1)
    checked_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    check_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
