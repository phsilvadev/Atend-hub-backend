from datetime import datetime,time,timedelta,date,timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select,func,case,and_,or_
from sqlalchemy.exc import IntegrityError
from app.models.ai_usage import AIUsage,AIPrice
from app.models.auth import Company,User
from app.core.security import now
from app.services.ai_accounting import price_usage
from app.services.platform_settings import reauthenticate
from app.services.platform_auth import audit

ZONE=ZoneInfo('America/Sao_Paulo')

def date_range(start,end):
    if start.year<2000 or end.year>2100 or start>end or (end-start).days>=366:raise HTTPException(422,'Informe um período válido de até 366 dias.')
    lower=int(datetime.combine(start,time.min,ZONE).timestamp())
    upper=int(datetime.combine(end+timedelta(days=1),time.min,ZONE).timestamp())
    return lower,upper


def overview(db,start,end,company_id=None,user_id=None,model='',status='all',pricing='all',offset=0,limit=20):
    lower,upper=date_range(start,end)
    shown_status=case((and_(AIUsage.status=='processing',AIUsage.created_at<now()-120),'interrupted'),else_=AIUsage.status)
    query=select(AIUsage).where(AIUsage.created_at>=lower,AIUsage.created_at<upper)
    if company_id:query=query.where(AIUsage.company_id==str(company_id))
    if user_id:query=query.where(AIUsage.user_id==str(user_id))
    if model:query=query.where(or_(AIUsage.model==model,AIUsage.resolved_model==model))
    if status!='all':query=query.where(shown_status==status)
    if pricing=='valued':query=query.where(AIUsage.cost_usd.is_not(None))
    if pricing=='unknown':query=query.where(AIUsage.cost_usd.is_(None))
    base=query.subquery()
    sums=db.execute(select(func.count(),func.coalesce(func.sum(base.c.input_tokens),0),func.coalesce(func.sum(base.c.output_tokens),0),func.coalesce(func.sum(base.c.cached_tokens),0),func.sum(base.c.cost_usd),func.count(base.c.cost_usd),func.sum(case((and_(base.c.input_tokens.is_not(None),base.c.output_tokens.is_not(None)),1),else_=0))).select_from(base)).one()
    total,input_tokens,output_tokens,cached_tokens,cost,valued,measured=sums
    cost_value=format(cost or Decimal('0'),'.18f')
    groups=[]
    grouped=db.execute(select(base.c.company_id,Company.name,func.count(),func.coalesce(func.sum(base.c.input_tokens),0),func.coalesce(func.sum(base.c.output_tokens),0),func.sum(base.c.cost_usd),func.count(base.c.cost_usd)).join(Company,Company.id==base.c.company_id).group_by(base.c.company_id,Company.name).order_by(func.sum(base.c.cost_usd).desc().nulls_last(),Company.name).limit(20)).all()
    for company,name,count,inputs,outputs,amount,priced in grouped:groups.append({'company_id':company,'company_name':name,'requests':count,'input_tokens':inputs,'output_tokens':outputs,'cost_usd':format(amount or Decimal('0'),'.18f') if priced else None,'unpriced':count-priced})
    records=db.execute(query.add_columns(Company.name,User.name,User.email).join(Company,Company.id==AIUsage.company_id).join(User,User.id==AIUsage.user_id).order_by(AIUsage.created_at.desc(),AIUsage.id).offset(offset).limit(limit)).all()
    items=[]
    for row,company,user,email in records:
        display='interrupted' if row.status=='processing' and row.created_at<now()-120 else row.status
        items.append({'id':row.id,'created_at':row.created_at,'company_id':row.company_id,'company_name':company,'user_name':user,'user_email':email,'feature':row.feature,'model':row.model,'resolved_model':row.resolved_model,'service_tier':row.service_tier,'status':display,'input_tokens':row.input_tokens,'output_tokens':row.output_tokens,'cached_tokens':row.cached_tokens,'pricing_status':row.pricing_status,'cost_usd':format(row.cost_usd,'.18f') if row.cost_usd is not None else None,'price_id':row.price_id})
    companies=[{'id':r.id,'name':r.name} for r in db.scalars(select(Company).order_by(Company.name,Company.id).limit(500))]
    users=[{'id':r.id,'name':r.name} for r in db.scalars(select(User).where(User.company_id==str(company_id)).order_by(User.name).limit(500))] if company_id else []
    models=sorted(set(db.scalars(select(AIUsage.model).distinct()).all())|set(db.scalars(select(AIUsage.resolved_model).where(AIUsage.resolved_model.is_not(None)).distinct()).all()))
    return {'items':items,'total':total,'summary':{'requests':total,'input_tokens':input_tokens,'output_tokens':output_tokens,'cached_tokens':cached_tokens,'measured_requests':measured or 0,'unmeasured_requests':total-(measured or 0),'valued_requests':valued,'unpriced_requests':total-valued,'estimated_cost_usd':cost_value if valued or total==0 else None},'by_company':groups,'companies':companies,'users':users,'models':models,'currency':'USD','timezone':'America/Sao_Paulo','feature_scope':'support','poll_seconds':30}


def price_output(row):
    return {'id':row.id,'model':row.model,'input_usd':str(row.input_usd),'cached_usd':str(row.cached_usd),'output_usd':str(row.output_usd),'effective_from':row.effective_from,'source_url':row.source_url,'created_at':row.created_at}


def create_price(db,context,data):
    reauthenticate(db,context,data.current_password)
    if data.cached_usd>data.input_usd:raise HTTPException(422,'O preço de cache não pode superar o de entrada.')
    if not 2000<=data.effective_from.year<=2100:raise HTTPException(422,'Informe uma data de vigência válida.')
    effective=int(datetime.combine(data.effective_from,time.min,timezone.utc).timestamp())
    if effective>now()+366*86400:raise HTTPException(422,'Data de vigência distante demais.')
    row=AIPrice(model=data.model,input_usd=data.input_usd,cached_usd=data.cached_usd,output_usd=data.output_usd,effective_from=effective,source_url=data.source_url,created_at=now())
    db.add(row)
    try:db.flush()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Já existe uma tarifa deste modelo nessa data. Cadastre uma nova vigência.') from None
    applied,remaining=apply_unpriced(db,row) if data.apply_to_unpriced else (0,0)
    audit(db,context.admin,'platform.ai_price.created',row.id);db.commit()
    return {**price_output(row),'applied_records':applied,'remaining_records':remaining}


def apply_unpriced(db,price):
    query=select(AIUsage).where(func.coalesce(AIUsage.resolved_model,AIUsage.model)==price.model,AIUsage.cost_usd.is_(None),AIUsage.pricing_status=='unknown_price',AIUsage.created_at>=price.effective_from)
    rows=db.scalars(query.order_by(AIUsage.created_at,AIUsage.id).limit(5000)).all()
    rates=list(db.scalars(select(AIPrice).where(AIPrice.model==price.model).order_by(AIPrice.effective_from.desc())).all())
    applied=0
    for usage in rows:
        applicable=next((rate for rate in rates if rate.effective_from<=usage.created_at),None)
        if applicable:usage.price_id=applicable.id
        price_usage(db,usage,legacy=usage.service_tier is None)
        if usage.cost_usd is not None:applied+=1
    db.flush()
    remaining=db.scalar(select(func.count()).select_from(query.subquery()))
    return applied,remaining


def apply_existing(db,context,price_id,password):
    reauthenticate(db,context,password)
    price=db.get(AIPrice,str(price_id))
    if not price:raise HTTPException(404,'Tarifa não encontrada.')
    applied,remaining=apply_unpriced(db,price)
    audit(db,context.admin,'platform.ai_price.applied',price.id);db.commit()
    return {'applied_records':applied,'remaining_records':remaining}
