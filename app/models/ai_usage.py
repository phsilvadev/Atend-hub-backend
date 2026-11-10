from decimal import Decimal
from sqlalchemy import String,Integer,Numeric,ForeignKey,ForeignKeyConstraint,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from app.core.database import Base
from app.models.auth import uid

class AIPrice(Base):
    __tablename__='ai_prices'
    __table_args__=(UniqueConstraint('model','effective_from',name='uq_ai_price_version'),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    model:Mapped[str]=mapped_column(String(120),index=True)
    input_usd:Mapped[Decimal]=mapped_column(Numeric(18,8))
    cached_usd:Mapped[Decimal]=mapped_column(Numeric(18,8))
    output_usd:Mapped[Decimal]=mapped_column(Numeric(18,8))
    effective_from:Mapped[int]=mapped_column(Integer)
    source_url:Mapped[str]=mapped_column(String(1000))
    created_at:Mapped[int]=mapped_column(Integer)

class AIUsage(Base):
    __tablename__='ai_usage'
    __table_args__=(ForeignKeyConstraint(['user_id','company_id'],['users.id','users.company_id']),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    company_id:Mapped[str]=mapped_column(String(36),index=True)
    user_id:Mapped[str]=mapped_column(String(36),index=True)
    feature:Mapped[str]=mapped_column(String(30),default='support')
    model:Mapped[str]=mapped_column(String(120),index=True)
    resolved_model:Mapped[str|None]=mapped_column(String(120),nullable=True)
    service_tier:Mapped[str|None]=mapped_column(String(30),nullable=True)
    status:Mapped[str]=mapped_column(String(20))
    input_tokens:Mapped[int|None]=mapped_column(Integer,nullable=True)
    cached_tokens:Mapped[int|None]=mapped_column(Integer,nullable=True)
    output_tokens:Mapped[int|None]=mapped_column(Integer,nullable=True)
    price_id:Mapped[str|None]=mapped_column(ForeignKey('ai_prices.id'),nullable=True)
    pricing_status:Mapped[str]=mapped_column(String(30),default='unknown_usage')
    cost_usd:Mapped[Decimal|None]=mapped_column(Numeric(30,18),nullable=True)
    created_at:Mapped[int]=mapped_column(Integer,index=True)
    finished_at:Mapped[int|None]=mapped_column(Integer,nullable=True)
