from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select,func
from app.core.database import get_db
from app.models.knowledge import PlatformAdmin
from app.schemas.platform_settings import AdminCreate,AdminEdit,OpenAIInput,ConfigAction
from app.services.platform_auth import platform_context
from app.services import platform_settings as service
router=APIRouter(prefix='/api/v1/platform',tags=['Configurações da plataforma'])

@router.get('/administrators')
def administrators(q:str=Query(default='',max_length=100),offset:int=Query(default=0,ge=0),limit:int=Query(default=20,ge=1,le=50),context=Depends(platform_context),db=Depends(get_db)):
    query=select(PlatformAdmin)
    if q.strip():query=query.where(PlatformAdmin.name.icontains(q.strip(),autoescape=True)|PlatformAdmin.email.icontains(q.strip(),autoescape=True))
    total=db.scalar(select(func.count()).select_from(query.subquery()))
    rows=db.scalars(query.order_by(PlatformAdmin.name,PlatformAdmin.id).offset(offset).limit(limit)).all()
    return {'items':[service.output(db,row,context.admin) for row in rows],'total':total}

@router.post('/administrators',status_code=201)
def create(data:AdminCreate,context=Depends(platform_context),db=Depends(get_db)):
    return service.create_admin(db,context,data)

@router.patch('/administrators/{admin_id}')
def edit(admin_id:UUID,data:AdminEdit,context=Depends(platform_context),db=Depends(get_db)):
    return service.edit_admin(db,context,admin_id,data)

@router.get('/settings/openai')
def settings(context=Depends(platform_context),db=Depends(get_db)):
    return service.config_output(db,context.admin)

@router.patch('/settings/openai')
def save(data:OpenAIInput,context=Depends(platform_context),db=Depends(get_db)):
    return service.save_config(db,context,data)

@router.post('/settings/openai/test')
def test(data:ConfigAction,context=Depends(platform_context),db=Depends(get_db)):
    return service.test_config(db,context,data)

@router.post('/settings/openai/remove')
def remove(data:ConfigAction,context=Depends(platform_context),db=Depends(get_db)):
    return service.remove_config(db,context,data)
