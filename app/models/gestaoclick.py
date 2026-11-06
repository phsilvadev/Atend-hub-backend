from sqlalchemy import ForeignKey,Integer,String,Text,JSON
from sqlalchemy.orm import Mapped,mapped_column
from app.core.database import Base

class GestaoClickConnection(Base):
    __tablename__='gestaoclick_connections'
    company_id: Mapped[str]=mapped_column(ForeignKey('companies.id'),primary_key=True)
    base_url: Mapped[str]=mapped_column(String(300))
    encrypted_credentials: Mapped[str|None]=mapped_column(Text,nullable=True)
    version: Mapped[int]=mapped_column(Integer)
    updated_at: Mapped[int]=mapped_column(Integer)

    stores: Mapped[list]=mapped_column(JSON,default=list)
    selected_store_id: Mapped[str|None]=mapped_column(String(40),nullable=True)
    tested_at: Mapped[int|None]=mapped_column(Integer,nullable=True)
    last_test_started_at: Mapped[int|None]=mapped_column(Integer,nullable=True)
    test_error_code: Mapped[str|None]=mapped_column(String(40),nullable=True)
