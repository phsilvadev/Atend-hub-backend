from sqlalchemy import String, Integer, Text, ForeignKey, ForeignKeyConstraint, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.models.auth import uid

class Customer(Base):
    __tablename__ = 'customers'
    __table_args__ = (UniqueConstraint('id', 'company_id', name='uq_customer_tenant'), UniqueConstraint('company_id', 'phone', name='uq_customer_phone'))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str] = mapped_column(ForeignKey('companies.id'), index=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(15))
    business_name: Mapped[str] = mapped_column(String(160), default='')
    created_at: Mapped[int] = mapped_column(Integer)

class Conversation(Base):
    __tablename__ = 'conversations'
    __table_args__ = (
        UniqueConstraint('id', 'company_id', name='uq_conversation_tenant'),
        UniqueConstraint('company_id', 'request_id', name='uq_conversation_request'),
        ForeignKeyConstraint(['customer_id', 'company_id'], ['customers.id', 'customers.company_id']),
        ForeignKeyConstraint(['assigned_user_id', 'company_id'], ['users.id', 'users.company_id']),
        Index('ix_conversation_tenant_updated', 'company_id', 'updated_at'),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str] = mapped_column(ForeignKey('companies.id'))
    customer_id: Mapped[str] = mapped_column(String(36))
    assigned_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    subject: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30), default='new')
    channel: Mapped[str] = mapped_column(String(20), default='manual')
    request_id: Mapped[str] = mapped_column(String(36))
    request_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[int] = mapped_column(Integer)
    closed_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

class ConversationMessage(Base):
    __tablename__ = 'conversation_messages'
    __table_args__ = (
        ForeignKeyConstraint(['conversation_id', 'company_id'], ['conversations.id', 'conversations.company_id']),
        ForeignKeyConstraint(['actor_id', 'company_id'], ['users.id', 'users.company_id']),
        UniqueConstraint('company_id', 'conversation_id', 'request_id', name='uq_message_request'),
        Index('ix_message_conversation_id', 'company_id', 'conversation_id', 'id'),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[str] = mapped_column(ForeignKey('companies.id'))
    conversation_id: Mapped[str] = mapped_column(String(36))
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    kind: Mapped[str] = mapped_column(String(30))
    body: Mapped[str] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[int] = mapped_column(Integer)
