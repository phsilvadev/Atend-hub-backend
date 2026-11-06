from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped,mapped_column
from app.core.database import Base

class WhatsAppOfficialConnection(Base):
    __tablename__='whatsapp_official_connections'
    company_id: Mapped[str]=mapped_column(ForeignKey('companies.id'),primary_key=True)
    phone_number_id: Mapped[str]=mapped_column(ForeignKey('whatsapp_numbers.phone_number_id'),unique=True)
    waba_id: Mapped[str]=mapped_column(String(40))
    encrypted_token: Mapped[str|None]=mapped_column(Text,nullable=True)
    display_phone_number: Mapped[str]=mapped_column(String(40))
    verified_name: Mapped[str]=mapped_column(String(160))
    diagnostics: Mapped[dict]=mapped_column(JSON,default=dict)
    active: Mapped[bool]=mapped_column(Boolean,default=True)
    verified_at: Mapped[int]=mapped_column(Integer)
    version: Mapped[int]=mapped_column(Integer,default=1)


class WhatsAppSignupAttempt(Base):
    __tablename__ = 'whatsapp_signup_attempts'
    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey('companies.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    session_id: Mapped[str] = mapped_column(ForeignKey('sessions.token_hash'))
    connection_version: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[int] = mapped_column(Integer, index=True)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)
    code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
