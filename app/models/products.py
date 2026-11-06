"""Tenant catalog and resumable imports; commercial values remain in the ERP."""
from sqlalchemy import ForeignKey, Integer, String, Text, Boolean, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class Product(Base):
    __tablename__ = 'products'
    __table_args__ = (UniqueConstraint('company_id', 'erp_id'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey('companies.id'), index=True)
    erp_id: Mapped[str] = mapped_column(String(40))
    code: Mapped[str] = mapped_column(String(160))
    name: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(Boolean)
    has_variations: Mapped[bool] = mapped_column(Boolean)
    synced_at: Mapped[int] = mapped_column(Integer)
    image_object: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_generation: Mapped[str | None] = mapped_column(String(40), nullable=True)
    image_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    image_updated_at: Mapped[int | None] = mapped_column(Integer, nullable=True)

class ProductSync(Base):
    __tablename__ = 'product_syncs'
    company_id: Mapped[str] = mapped_column(ForeignKey('companies.id'), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36))
    credential_version: Mapped[int] = mapped_column(Integer)
    store_id: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(16))
    next_page: Mapped[int] = mapped_column(Integer)
    total_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[int] = mapped_column(Integer)
    completed_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_success_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    lease_until: Mapped[int | None] = mapped_column(Integer, nullable=True)

class ProductSyncItem(Base):
    __tablename__ = 'product_sync_items'
    company_id: Mapped[str] = mapped_column(ForeignKey('companies.id'), primary_key=True)
    erp_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)
