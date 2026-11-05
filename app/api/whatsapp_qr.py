import hashlib
import hmac
import json
from uuid import uuid4, UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import update, select
from sqlalchemy.orm import Session
from pydantic import Field
from starlette.concurrency import run_in_threadpool
from app.api.dependencies import admin_context, Context
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import now
from app.models.auth import Company
from app.models.whatsapp import WhatsAppNumber
from app.models.whatsapp_qr import WhatsAppQRConnection
from app.schemas.auth import StrictInput
from app.integrations.whatsapp_qr import gateway, configured
from app.services.auth import audit
from app.services.whatsapp import receive

router=APIRouter(tags=['WhatsApp QR'])
QR_WEBHOOK_PATH='/api/v1/webhooks/whatsapp-qr'
PREFIX='/api/v1/integrations/whatsapp-qr'

class Empty(StrictInput):
    pass

class Incoming(StrictInput):
    session_id: UUID
    external_id: str = Field(min_length=1,max_length=200)
    sender: str = Field(pattern=r'^\d{10,15}$')
    name: str = Field(default='',max_length=120)
    body: str = Field(min_length=1,max_length=4096)
    timestamp: int = Field(ge=0)

def output(company_id,data=None):
    return {'company_id':company_id,'enabled':configured(),'status':'disconnected','qr_data_url':None,'qr_expires_at':None,'phone':None,**(data or {})}

@router.get(PREFIX)
def status(context: Context=Depends(admin_context),db: Session=Depends(get_db)):
    connection=db.get(WhatsAppQRConnection,context.company.id)
    if not connection or not connection.active or not configured():
        return output(context.company.id)
    return output(context.company.id,gateway('GET',connection.session_id))

@router.post(PREFIX+'/connect')
def connect(data: Empty,context: Context=Depends(admin_context),db: Session=Depends(get_db)):
    if not configured():
        raise HTTPException(503,'A conexão por QR Code ainda não está disponível. Solicite a ativação ao suporte.')
    # Serializes concurrent administrative connect/disconnect for this tenant.
    db.execute(update(Company).where(Company.id==context.company.id).values(name=Company.name))
    connection=db.get(WhatsAppQRConnection,context.company.id)
    if not connection:
        connection=WhatsAppQRConnection(company_id=context.company.id,session_id=str(uuid4()),active=True)
        db.add(connection)
    elif not connection.active:
        gateway('DELETE',connection.session_id)
        connection.session_id=str(uuid4())
        connection.active=True
    alias='qr-'+connection.session_id
    if not db.get(WhatsAppNumber,alias):
        db.add(WhatsAppNumber(phone_number_id=alias,company_id=context.company.id,waba_id='qr',active=True))
    result=gateway('POST',connection.session_id)
    audit(db,context.user,'whatsapp_qr.connect_requested')
    db.commit()
    return output(context.company.id,result)

@router.post(PREFIX+'/disconnect')
def disconnect(data: Empty,context: Context=Depends(admin_context),db: Session=Depends(get_db)):
    db.execute(update(Company).where(Company.id==context.company.id).values(name=Company.name))
    connection=db.get(WhatsAppQRConnection,context.company.id)
    if connection:
        connection.active=False
        db.execute(update(WhatsAppNumber).where(WhatsAppNumber.phone_number_id=='qr-'+connection.session_id).values(active=False))
        audit(db,context.user,'whatsapp_qr.disconnect_requested')
        db.commit()  # Block callbacks even if remote logout fails; retry is safe.
        gateway('DELETE',connection.session_id)
    return output(context.company.id)

def process(db,event):
    connection=db.scalar(select(WhatsAppQRConnection).where(WhatsAppQRConnection.session_id==str(event.session_id),WhatsAppQRConnection.active.is_(True)))
    if not connection:
        return
    receive(db,{'object':'whatsapp_business_account','entry':[{'id':'qr','changes':[{'field':'messages','value':{'metadata':{'phone_number_id':'qr-'+connection.session_id},'contacts':[{'wa_id':event.sender,'profile':{'name':event.name}}],'messages':[{'id':event.external_id,'from':event.sender,'type':'text','timestamp':event.timestamp,'text':{'body':event.body}}]}}]}]},channel='whatsapp_qr')

@router.post(QR_WEBHOOK_PATH)
async def callback(request: Request,db: Session=Depends(get_db)):
    if not configured():
        raise HTTPException(503,'Conexão indisponível.')
    raw=bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw)>65536:
            raise HTTPException(413,'Evento muito grande.')
    timestamp=request.headers.get('x-bridge-timestamp','')
    if not timestamp.isdecimal() or len(timestamp)>12 or abs(now()-int(timestamp))>300:
        raise HTTPException(401,'Evento expirado.')
    secret=get_settings().whatsapp_qr_bridge_token.get_secret_value()
    signature=hmac.new(secret.encode(),timestamp.encode()+b'.'+raw,hashlib.sha256).hexdigest()
    if not hmac.compare_digest(request.headers.get('x-bridge-signature','').encode(),signature.encode()):
        raise HTTPException(401,'Assinatura inválida.')
    try:
        event=Incoming.model_validate(json.loads(raw))
    except (ValueError,TypeError):
        raise HTTPException(400,'Evento inválido.')
    await run_in_threadpool(process,db,event)
    return {'status':'ok'}
