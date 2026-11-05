import re
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import Field,SecretStr,field_validator,model_validator
from sqlalchemy import select,update,func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.dependencies import admin_context,Context
from app.core.database import get_db
from app.core.config import get_settings
from app.core.security import now,throttle
from app.core.integration_secrets import configured,key_bytes,encrypt_token,decrypt_token
from app.models.auth import Company
from app.models.whatsapp import WhatsAppNumber,WhatsAppReceipt
from app.models.whatsapp_official import WhatsAppOfficialConnection as Connection
from app.schemas.auth import StrictInput
from app.integrations.whatsapp_official import validate_credentials,setup_connection
from app.services.auth import audit

router=APIRouter(prefix='/api/v1/integrations/whatsapp-official',tags=['WhatsApp oficial'])

class Credentials(StrictInput):
    phone_number_id: str=Field(pattern=r'^\d{1,40}$')
    waba_id: str=Field(pattern=r'^\d{1,40}$')
    access_token: SecretStr|None=None
    version: int=Field(ge=0)

    @field_validator('access_token')
    @classmethod
    def token_format(cls,value):
        if value is not None and not re.fullmatch(r'[\x21-\x7e]{20,4096}',value.get_secret_value()):
            raise ValueError('Token inválido')
        return value

class Version(StrictInput):
    version: int=Field(ge=0)

def output(db,company_id):
    row=db.get(Connection,company_id)
    latest=db.scalar(select(func.max(WhatsAppReceipt.received_at)).where(WhatsAppReceipt.phone_number_id==row.phone_number_id)) if row and row.active else None
    settings=get_settings()
    return {'company_id':company_id,'enabled':configured(),'status':('receiving' if latest and latest>=row.verified_at else 'validated') if row and row.active else 'disconnected',
        'phone_number_id':row.phone_number_id if row else '', 'waba_id':row.waba_id if row else '',
        'display_phone_number':row.display_phone_number if row else '', 'verified_name':row.verified_name if row else '',
        'has_token':bool(row and row.encrypted_token),'verified_at':row.verified_at if row else None,'last_received_at':latest,
        'diagnostics':row.diagnostics if row else {},
        'platform_app_configured':bool(settings.whatsapp_app_id and settings.whatsapp_app_secret.get_secret_value()),
        'version':row.version if row else 0,'webhook_url':settings.whatsapp_public_webhook_url or None,
        'webhook_configured':bool(settings.whatsapp_app_secret.get_secret_value() and settings.whatsapp_verify_token.get_secret_value())}

@router.get('')
def get_connection(context: Context=Depends(admin_context),db: Session=Depends(get_db)):
    return output(db,context.company.id)

@router.post('/connect')
def connect(data: Credentials,context: Context=Depends(admin_context),db: Session=Depends(get_db)):
    key_bytes()  # Refuse to handle/persist credentials if encryption is not configured.
    throttle(db,f'whatsapp-official:{context.company.id}',10)
    existing=db.get(Connection,context.company.id)
    if (existing.version if existing else 0)!=data.version:
        raise HTTPException(409,'A conexão foi atualizada. Recarregue antes de salvar.')
    number=db.get(WhatsAppNumber,data.phone_number_id)
    if number and (number.company_id!=context.company.id or number.waba_id!=data.waba_id):
        raise HTTPException(409,'Não foi possível vincular este número. Contate o suporte.')
    token=data.access_token.get_secret_value() if data.access_token else None
    if not token:
        if not existing or not existing.active or not existing.encrypted_token or existing.phone_number_id!=data.phone_number_id or existing.waba_id!=data.waba_id:
            raise HTTPException(422,'Informe um novo token para cadastrar ou alterar os identificadores da conexão.')
        token=decrypt_token(existing.encrypted_token,context.company.id,existing.phone_number_id,existing.waba_id)
    verified=validate_credentials(token,data.phone_number_id,data.waba_id)
    encrypted=encrypt_token(token,context.company.id,data.phone_number_id,data.waba_id)
    db.execute(update(Company).where(Company.id==context.company.id).values(name=Company.name))
    db.expire_all()
    existing=db.get(Connection,context.company.id)
    if context.user.role!='admin' or not context.user.active or context.session.revoked or context.session.expires_at<=now() or not context.company.active or (context.company.plan=='trial' and context.company.trial_ends_at<=now()):
        db.rollback()
        raise HTTPException(403,'O acesso administrativo foi alterado. Entre novamente para continuar.')
    if (existing.version if existing else 0)!=data.version:
        db.rollback()
        raise HTTPException(409,'A conexão foi atualizada. Recarregue antes de salvar.')
    try:
        number=db.get(WhatsAppNumber,data.phone_number_id)
        if number and (number.company_id!=context.company.id or number.waba_id!=data.waba_id):
            raise HTTPException(409,'Não foi possível vincular este número. Contate o suporte.')
        if existing and existing.phone_number_id!=data.phone_number_id:
            old=db.get(WhatsAppNumber,existing.phone_number_id)
            if old:
                old.active=False
        if not number:
            number=WhatsAppNumber(phone_number_id=data.phone_number_id,company_id=context.company.id,waba_id=data.waba_id,active=True)
            db.add(number)
            db.flush()
        number.active=True
        if not existing:
            existing=Connection(company_id=context.company.id)
            db.add(existing)
        existing.phone_number_id=data.phone_number_id
        existing.waba_id=data.waba_id
        existing.encrypted_token=encrypted
        existing.display_phone_number=verified['display_phone_number']
        existing.verified_name=verified['verified_name']
        existing.diagnostics=verified['diagnostics']
        existing.active=True
        existing.verified_at=now()
        existing.version=data.version+1
        audit(db,context.user,'whatsapp_official.credentials_validated')
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,'Não foi possível salvar a conexão. Atualize e tente novamente.')
    return output(db,context.company.id)

@router.post('/disconnect')
def disconnect(data: Version,context: Context=Depends(admin_context),db: Session=Depends(get_db)):
    db.execute(update(Company).where(Company.id==context.company.id).values(name=Company.name))
    row=db.get(Connection,context.company.id)
    if (row.version if row else 0)!=data.version:
        raise HTTPException(409,'A conexão foi atualizada. Recarregue antes de desconectar.')
    if row:
        row.encrypted_token=None
        row.active=False
        row.version+=1
        number=db.get(WhatsAppNumber,row.phone_number_id)
        if number:
            number.active=False
        audit(db,context.user,'whatsapp_official.disconnected')
        db.commit()
    return output(db,context.company.id)


class Setup(Version):
    action: Literal['subscribe','register']
    confirm: Literal[True]
    pin: SecretStr|None=None

    @model_validator(mode='after')
    def pin_format(self):
        if self.action=='register' and (self.pin is None or not re.fullmatch(r'\d{6}',self.pin.get_secret_value())):
            raise ValueError('PIN de seis dígitos obrigatório')
        if self.action=='subscribe' and self.pin is not None:
            raise ValueError('PIN não utilizado nesta operação')
        return self

@router.post('/setup')
def setup(data: Setup,context: Context=Depends(admin_context),db: Session=Depends(get_db)):
    throttle(db,f'whatsapp-official-setup:{context.company.id}',10)
    # Serialize setup/removal so another admin cannot switch credentials mid-operation.
    db.execute(update(Company).where(Company.id==context.company.id).values(name=Company.name))
    row=db.get(Connection,context.company.id)
    if not row or not row.active or not row.encrypted_token:
        raise HTTPException(409,'Cadastre e valide as credenciais antes desta operação.')
    if row.version!=data.version:
        raise HTTPException(409,'A conexão foi atualizada. Recarregue antes de continuar.')
    token=decrypt_token(row.encrypted_token,context.company.id,row.phone_number_id,row.waba_id)
    row.diagnostics=setup_connection(token,row.phone_number_id,row.waba_id,data.action,data.pin.get_secret_value() if data.pin else None)
    row.version+=1
    audit(db,context.user,'whatsapp_official.'+data.action+'_requested')
    db.commit()
    return output(db,context.company.id)
