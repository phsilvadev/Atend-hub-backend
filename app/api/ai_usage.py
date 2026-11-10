from datetime import date,datetime,timedelta
from uuid import UUID
from typing import Literal
from fastapi import APIRouter,Depends,Query
from sqlalchemy import select
from app.core.database import get_db
from app.services.platform_auth import platform_context
from app.services import ai_usage as service
from app.models.ai_usage import AIPrice
from app.schemas.ai_usage import PriceInput,ApplyPriceInput
router=APIRouter(prefix='/api/v1/platform/ai-usage',tags=['Consumo de IA'])
@router.get('')
def overview(start:date|None=None,end:date|None=None,company_id:UUID|None=None,user_id:UUID|None=None,model:str=Query(default='',max_length=120),status:Literal['all','processing','complete','failed','interrupted']='all',pricing:Literal['all','valued','unknown']='all',offset:int=Query(default=0,ge=0),limit:int=Query(default=20,ge=1,le=50),context=Depends(platform_context),db=Depends(get_db)):
    today=datetime.now(service.ZONE).date()
    return service.overview(db,start or today-timedelta(days=29),end or today,company_id,user_id,model,status,pricing,offset,limit)
@router.get('/prices')
def prices(offset:int=Query(default=0,ge=0),limit:int=Query(default=20,ge=1,le=50),context=Depends(platform_context),db=Depends(get_db)):
    from sqlalchemy import func
    total=db.scalar(select(func.count()).select_from(AIPrice))
    rows=db.scalars(select(AIPrice).order_by(AIPrice.effective_from.desc(),AIPrice.model).offset(offset).limit(limit)).all()
    return {'items':[service.price_output(row) for row in rows],'total':total,'currency':'USD'}
@router.post('/prices',status_code=201)
def create(data:PriceInput,context=Depends(platform_context),db=Depends(get_db)):
    return service.create_price(db,context,data)

@router.post('/prices/{price_id}/apply')
def apply(price_id:UUID,data:ApplyPriceInput,context=Depends(platform_context),db=Depends(get_db)):
    return service.apply_existing(db,context,price_id,data.current_password)
