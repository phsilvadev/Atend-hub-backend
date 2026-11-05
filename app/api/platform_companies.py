from typing import Literal
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, or_, exists
from app.core.database import get_db
from app.core.security import now
from app.models.auth import Company, CompanyProfile, User, Plan
from app.services.platform_auth import platform_context, audit

router=APIRouter(prefix='/api/v1/platform/companies',tags=['Empresas da plataforma'])

@router.get('')
def companies(q:str=Query(default='',max_length=100),status:Literal['all','active','trial','trial_expired','inactive']='all',offset:int=Query(default=0,ge=0),limit:int=Query(default=20,ge=1,le=100),context=Depends(platform_context),db=Depends(get_db)):
    timestamp=now()
    conditions={
        'active': (Company.active.is_(True) & (Company.plan != 'trial')),
        'trial': (Company.active.is_(True) & (Company.plan == 'trial') & (Company.trial_ends_at > timestamp)),
        'trial_expired': (Company.active.is_(True) & (Company.plan == 'trial') & (Company.trial_ends_at <= timestamp)),
        'inactive': Company.active.is_(False),
    }
    query=select(Company,CompanyProfile,Plan).outerjoin(CompanyProfile,CompanyProfile.company_id == Company.id).outerjoin(Plan,Plan.code == Company.plan)
    if q.strip():
        term=q.strip()
        import re
        tax=re.sub(r'[.\-/\s]','',term).upper()
        query=query.where(or_(Company.name.icontains(term,autoescape=True),CompanyProfile.legal_name.icontains(term,autoescape=True),CompanyProfile.tax_id.icontains(tax or term,autoescape=True),CompanyProfile.email.icontains(term,autoescape=True),exists(select(User.id).where(User.company_id == Company.id,User.role == 'admin',User.email.icontains(term,autoescape=True)))))
    if status != 'all': query=query.where(conditions[status])
    total=db.scalar(select(func.count()).select_from(query.subquery()))
    rows=db.execute(query.order_by(Company.trial_started_at.desc(),Company.id).offset(offset).limit(limit)).all()
    ids=[company.id for company,_,_ in rows]
    admins=db.scalars(select(User).where(User.company_id.in_(ids),User.role == 'admin',User.active.is_(True)).order_by(User.name,User.id)).all() if ids else []
    admin_map={}
    for user in admins:
        admin_map.setdefault(user.company_id,{'name':user.name,'email':user.email})
    items=[]
    for company,profile,plan in rows:
        state='inactive' if not company.active else ('trial_expired' if company.trial_ends_at <= timestamp else 'trial') if company.plan == 'trial' else 'active'
        items.append({'id':company.id,'name':company.name,'legal_name':profile.legal_name if profile else '', 'tax_id':profile.tax_id if profile else '', 'email':profile.email if profile else '', 'administrator':admin_map.get(company.id), 'plan_code':company.plan,'plan_name':'Teste gratuito' if company.plan == 'trial' else plan.name if plan else company.plan,'status':state,'registered_at':company.trial_started_at,'trial_ends_at':company.trial_ends_at if company.plan == 'trial' else None})
    summary={key:db.scalar(select(func.count()).select_from(Company).where(condition)) for key,condition in conditions.items()}
    summary['total']=db.scalar(select(func.count()).select_from(Company))
    audit(db,context.admin,'platform.companies.list');db.commit()
    return {'items':items,'total':total,'summary':summary}
