from sqlalchemy import String, Integer, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class WhatsAppNumber(Base):
    __tablename__ = 'whatsapp_numbers'
    phone_number_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey('companies.id'), index=True)
    waba_id: Mapped[str] = mapped_column(String(40))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)

class WhatsAppReceipt(Base):
    __tablename__ = 'whatsapp_receipts'
    phone_number_id: Mapped[str] = mapped_column(ForeignKey('whatsapp_numbers.phone_number_id'), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey('conversation_messages.id'))
    received_at: Mapped[int] = mapped_column(Integer)
