"""Durable AI consumption without prompts; versioned standard-text rates."""
from alembic import op
import sqlalchemy as sa
from decimal import Decimal
from uuid import uuid4
revision='20261110_ai_usage'
down_revision='20261110_support'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('ai_prices',sa.Column('id',sa.String(36),primary_key=True),sa.Column('model',sa.String(120),nullable=False),sa.Column('input_usd',sa.Numeric(18,8),nullable=False),sa.Column('cached_usd',sa.Numeric(18,8),nullable=False),sa.Column('output_usd',sa.Numeric(18,8),nullable=False),sa.Column('effective_from',sa.Integer(),nullable=False),sa.Column('source_url',sa.String(1000),nullable=False),sa.Column('created_at',sa.Integer(),nullable=False),sa.UniqueConstraint('model','effective_from',name='uq_ai_price_version'))
    op.create_index('ix_ai_prices_model','ai_prices',['model'])
    op.create_table('ai_usage',sa.Column('id',sa.String(36),primary_key=True),sa.Column('company_id',sa.String(36),nullable=False),sa.Column('user_id',sa.String(36),nullable=False),sa.Column('feature',sa.String(30),nullable=False),sa.Column('model',sa.String(120),nullable=False),sa.Column('resolved_model',sa.String(120),nullable=True),sa.Column('service_tier',sa.String(30),nullable=True),sa.Column('status',sa.String(20),nullable=False),sa.Column('input_tokens',sa.Integer(),nullable=True),sa.Column('cached_tokens',sa.Integer(),nullable=True),sa.Column('output_tokens',sa.Integer(),nullable=True),sa.Column('price_id',sa.String(36),sa.ForeignKey('ai_prices.id'),nullable=True),sa.Column('pricing_status',sa.String(30),nullable=False),sa.Column('cost_usd',sa.Numeric(30,18),nullable=True),sa.Column('created_at',sa.Integer(),nullable=False),sa.Column('finished_at',sa.Integer(),nullable=True),sa.ForeignKeyConstraint(['user_id','company_id'],['users.id','users.company_id']))
    for col in ['company_id','user_id','model','created_at']:op.create_index('ix_ai_usage_'+col,'ai_usage',[col])
    db=op.get_bind()
    prices=sa.table('ai_prices',sa.column('id',sa.String),sa.column('model',sa.String),sa.column('input_usd',sa.Numeric),sa.column('cached_usd',sa.Numeric),sa.column('output_usd',sa.Numeric),sa.column('effective_from',sa.Integer),sa.column('created_at',sa.Integer),sa.column('source_url',sa.String))
    # Published standard text rates checked 2026-11-10, USD / 1M tokens. Not inferred for other models.
    effective=1794268800
    seeded=[]
    for model,rates in [('gpt-4.1-mini',('0.40','0.10','1.60')),('gpt-4.1',('2.00','0.50','8.00')),('gpt-4.1-nano',('0.10','0.025','0.40'))]:
        for alias in [model,model+'-2025-04-14']:
            price_id=str(uuid4());seeded.append((price_id,alias,rates))
            db.execute(prices.insert().values(id=price_id,model=alias,input_usd=Decimal(rates[0]),cached_usd=Decimal(rates[1]),output_usd=Decimal(rates[2]),effective_from=effective,created_at=effective,source_url='https://developers.openai.com/api/docs/models/'+model))
    # Existing support records lack cache/tier details: preserve the measurements, not a fictitious zero cost.
    db.execute(sa.text("INSERT INTO ai_usage (id,company_id,user_id,feature,model,status,input_tokens,output_tokens,pricing_status,created_at,finished_at) SELECT id,company_id,user_id,'support',model,status,input_tokens,output_tokens,CASE WHEN input_tokens IS NOT NULL AND output_tokens IS NOT NULL THEN 'unknown_price' ELSE 'unknown_usage' END,created_at,CASE WHEN status='processing' THEN NULL ELSE created_at END FROM support_turns"))
    usage=sa.table('ai_usage',sa.column('model'),sa.column('created_at'),sa.column('input_tokens',sa.Integer),sa.column('output_tokens',sa.Integer),sa.column('price_id'),sa.column('cost_usd',sa.Numeric(30,18)),sa.column('pricing_status'))
    for price_id,model,rates in seeded:
        db.execute(usage.update().where(usage.c.model==model,usage.c.created_at>=effective,usage.c.input_tokens.is_not(None),usage.c.output_tokens.is_not(None)).values(price_id=price_id,pricing_status='estimated_legacy',cost_usd=(usage.c.input_tokens*sa.literal(Decimal(rates[0]),type_=sa.Numeric)+usage.c.output_tokens*sa.literal(Decimal(rates[2]),type_=sa.Numeric))/sa.literal(Decimal(1000000),type_=sa.Numeric)))

def downgrade():
    op.drop_table('ai_usage');op.drop_table('ai_prices')
