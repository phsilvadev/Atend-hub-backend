from sqlalchemy import String,Integer,Text,JSON,ForeignKey,ForeignKeyConstraint,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from app.core.database import Base
from app.models.auth import uid

class SupportThread(Base):
    __tablename__='support_threads'
    __table_args__=(ForeignKeyConstraint(['user_id','company_id'],['users.id','users.company_id']),)
    company_id:Mapped[str]=mapped_column(String(36),primary_key=True)
    user_id:Mapped[str]=mapped_column(String(36),primary_key=True)
    pending_id:Mapped[str|None]=mapped_column(String(36),nullable=True)
    pending_at:Mapped[int]=mapped_column(Integer,default=0)
    sequence:Mapped[int]=mapped_column(Integer,default=0)

class SupportTurn(Base):
    __tablename__='support_turns'
    __table_args__=(UniqueConstraint('company_id','user_id','request_id',name='uq_support_request'),ForeignKeyConstraint(['user_id','company_id'],['users.id','users.company_id']))
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    company_id:Mapped[str]=mapped_column(String(36),index=True)
    user_id:Mapped[str]=mapped_column(String(36),index=True)
    request_id:Mapped[str]=mapped_column(String(36))
    sequence:Mapped[int]=mapped_column(Integer)
    question:Mapped[str]=mapped_column(Text)
    answer:Mapped[str|None]=mapped_column(Text,nullable=True)
    status:Mapped[str]=mapped_column(String(20))
    error_code:Mapped[str|None]=mapped_column(String(30),nullable=True)
    model:Mapped[str]=mapped_column(String(120))
    config_version:Mapped[int]=mapped_column(Integer)
    input_tokens:Mapped[int|None]=mapped_column(Integer,nullable=True)
    output_tokens:Mapped[int|None]=mapped_column(Integer,nullable=True)
    sources:Mapped[list]=mapped_column(JSON,default=list)
    created_at:Mapped[int]=mapped_column(Integer,index=True)

class SupportQuota(Base):
    __tablename__='support_quotas'
    scope:Mapped[str]=mapped_column(String(120),primary_key=True)
    day:Mapped[int]=mapped_column(Integer,primary_key=True)
    used:Mapped[int]=mapped_column(Integer,default=0)
