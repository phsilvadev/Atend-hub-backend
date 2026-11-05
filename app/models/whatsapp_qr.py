from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class WhatsAppQRConnection(Base):
    __tablename__ = 'whatsapp_qr_connections'
    company_id: Mapped[str] = mapped_column(ForeignKey('companies.id'), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
