from sqlalchemy import ForeignKey,Integer,String,Text
from sqlalchemy.orm import Mapped,mapped_column
from app.core.database import Base

class GestaoClickConnection(Base):
    __tablename__='gestaoclick_connections'
    company_id: Mapped[str]=mapped_column(ForeignKey('companies.id'),primary_key=True)
    base_url: Mapped[str]=mapped_column(String(300))
    encrypted_credentials: Mapped[str|None]=mapped_column(Text,nullable=True)
    version: Mapped[int]=mapped_column(Integer)
    updated_at: Mapped[int]=mapped_column(Integer)
