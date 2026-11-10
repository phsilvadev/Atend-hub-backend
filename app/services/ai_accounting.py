"""Reusable accounting boundary. No question, answer, key or prompt is copied here."""
from decimal import Decimal,ROUND_HALF_UP
from sqlalchemy import select
from app.core.security import now
from app.models.ai_usage import AIUsage,AIPrice

MILLION=Decimal(1000000)
PRECISION=Decimal('0.000000000000000001')

def calculate(input_tokens,cached_tokens,output_tokens,price):
    if type(input_tokens) is not int or type(output_tokens) is not int or input_tokens<0 or output_tokens<0:return None,'unknown_usage'
    if not price:return None,'unknown_price'
    if cached_tokens is not None and (type(cached_tokens) is not int or not 0<=cached_tokens<=input_tokens):return None,'unknown_usage'
    cached=cached_tokens or 0
    amount=((Decimal(input_tokens-cached)*price.input_usd)+(Decimal(cached)*price.cached_usd)+(Decimal(output_tokens)*price.output_usd))/MILLION
    return amount.quantize(PRECISION,rounding=ROUND_HALF_UP),'calculated' if cached_tokens is not None else 'estimated_cache'


def price_for(db,model,timestamp,known_at=None):
    query=select(AIPrice).where(AIPrice.model==model,AIPrice.effective_from<=timestamp)
    if known_at is not None:query=query.where(AIPrice.created_at<=known_at)
    return db.scalar(query.order_by(AIPrice.effective_from.desc()).limit(1))


def price_usage(db,row,legacy=False,known_at=None):
    if row.service_tier not in (None,'default'):
        row.cost_usd=None;row.pricing_status='unknown_tier';return
    price=db.get(AIPrice,row.price_id) if row.price_id else price_for(db,row.resolved_model or row.model,row.created_at,known_at)
    amount,status=calculate(row.input_tokens,row.cached_tokens,row.output_tokens,price)
    row.cost_usd=amount;row.pricing_status=status
    if price:row.price_id=price.id
    if legacy and amount is not None:row.pricing_status='estimated_legacy'


def start(db,turn):
    row=AIUsage(id=turn.id,company_id=turn.company_id,user_id=turn.user_id,feature='support',model=turn.model,status='processing',created_at=turn.created_at,pricing_status='unknown_usage')
    price=price_for(db,turn.model,turn.created_at,turn.created_at)
    if price:row.price_id=price.id
    db.add(row)


def finish(db,turn_id,status,tokens):
    row=db.get(AIUsage,turn_id)
    if not row or row.finished_at is not None:return
    row.status=status;row.finished_at=now()
    row.input_tokens=tokens.get('input_tokens');row.output_tokens=tokens.get('output_tokens');row.cached_tokens=tokens.get('cached_tokens')
    row.service_tier=tokens.get('service_tier')
    actual=tokens.get('resolved_model')
    if isinstance(actual,str) and len(actual)<=120 and actual!=row.model:
        row.resolved_model=actual;row.price_id=None
    price_usage(db,row,known_at=row.created_at)
