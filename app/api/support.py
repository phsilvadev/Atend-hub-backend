from fastapi import APIRouter,Depends
from app.core.database import get_db
from app.api.dependencies import active_tenant
from app.schemas.support import SupportInput
from app.services import support
router=APIRouter(prefix='/api/v1/support',tags=['Suporte da plataforma'])
@router.get('/messages')
def history(context=Depends(active_tenant),db=Depends(get_db)):
    return support.history(db,context)
@router.post('/messages')
def send(data:SupportInput,context=Depends(active_tenant),db=Depends(get_db)):
    return support.send(db,context,data)
