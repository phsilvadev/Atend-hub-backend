"""Tenant configuration and explicit read-only access check against the documented ERP."""
import base64
import ipaddress
import json
import os
import re
from urllib.parse import urlsplit
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import APIRouter,Depends,HTTPException
from pydantic import Field,SecretStr,field_validator
from sqlalchemy import update
from sqlalchemy.orm import Session
from app.api.dependencies import admin_context,Context
from app.core.database import get_db
from app.core.integration_secrets import configured,key_bytes
from app.core.security import now,throttle
from app.models.auth import Company,User,Session as AuthSession
from app.models.gestaoclick import GestaoClickConnection as Connection
from app.schemas.auth import StrictInput
from app.services.auth import audit
from app.integrations.gestaoclick import list_stores,ERPError

router=APIRouter(prefix='/api/v1/integrations/gestaoclick',tags=['GestãoClick'])

class Version(StrictInput):
    version: int=Field(ge=0)

class Credentials(Version):
    base_url: str=Field(max_length=300)
    access_token: SecretStr|None=None
    secret_access_token: SecretStr|None=None

    @field_validator('base_url')
    @classmethod
    def valid_url(cls,value):
        try:
            parsed=urlsplit(value.strip())
            host=parsed.hostname or ''
            if parsed.scheme!='https' or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.port not in (None,443) or parsed.path.rstrip('/') not in ('/api','/v1') or not re.fullmatch(r'[a-z0-9.-]+',host) or '.' not in host or host.endswith(('.local','.localhost','.internal')):
                raise ValueError()
            try:
                ipaddress.ip_address(host)
            except ValueError:
                pass
            else:
                raise ValueError()
            return f'https://{host}{parsed.path.rstrip("/")}'
        except ValueError:
            raise ValueError('Informe o endereço HTTPS /api ou /v1 da documentação da sua conta, sem credenciais ou parâmetros.')

    @field_validator('access_token','secret_access_token')
    @classmethod
    def valid_secret(cls,value):
        if value is not None and not re.fullmatch(r'[\x21-\x7e]{1,4096}',value.get_secret_value()):
            raise ValueError('Credencial inválida')
        return value

def aad(company_id,url):
    return f'atendehub:gestaoclick:v1:{company_id}:{url}'.encode()

def encrypt(credentials,company_id,url):
    nonce=os.urandom(12)
    data=AESGCM(key_bytes()).encrypt(nonce,json.dumps(credentials).encode(),aad(company_id,url))
    return 'v1:'+base64.urlsafe_b64encode(nonce+data).decode()

def decrypt(ciphertext,company_id,url):
    try:
        if not ciphertext.startswith('v1:'):
            raise ValueError()
        raw=base64.b64decode(ciphertext[3:],altchars=b'-_',validate=True)
        return json.loads(AESGCM(key_bytes()).decrypt(raw[:12],raw[12:],aad(company_id,url)))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503,'Não foi possível acessar as credenciais protegidas. Contate o suporte.')

def output(db,company_id):
    row=db.get(Connection,company_id)
    status='not_configured'
    if row and row.encrypted_credentials:
        status='test_failed' if row.test_error_code else 'access_validated' if row.tested_at else 'credentials_saved'
    return {'company_id':company_id,'enabled':configured(),'base_url':row.base_url if row else '',
        'has_credentials':bool(row and row.encrypted_credentials),'status':status,
        'version':row.version if row else 0,'updated_at':row.updated_at if row else None,
        'stores':row.stores if row else [],'selected_store_id':row.selected_store_id if row else None,
        'tested_at':row.tested_at if row else None,'test_error_code':row.test_error_code if row else None}


@router.get('')
def get_configuration(context: Context=Depends(admin_context),db: Session=Depends(get_db)):
    return output(db,context.company.id)

@router.post('')
def save(data: Credentials,context: Context=Depends(admin_context),db: Session=Depends(get_db)):
    key_bytes()
    db.execute(update(Company).where(Company.id==context.company.id).values(name=Company.name))
    row=db.get(Connection,context.company.id)
    if (row.version if row else 0)!=data.version:
        raise HTTPException(409,'A configuração foi atualizada. Recarregue antes de salvar.')
    access=data.access_token.get_secret_value() if data.access_token else None
    secret=data.secret_access_token.get_secret_value() if data.secret_access_token else None
    previous={}
    if not access or not secret:
        if not row or not row.encrypted_credentials or row.base_url!=data.base_url:
            raise HTTPException(422,'Informe as duas credenciais para cadastrar ou alterar o endereço da API.')
        previous=decrypt(row.encrypted_credentials,context.company.id,row.base_url)
    credentials={'access_token':access or previous['access_token'],'secret_access_token':secret or previous['secret_access_token']}
    if not row:
        row=Connection(company_id=context.company.id)
        db.add(row)
    changed=bool(access or secret or row.base_url!=data.base_url or not row.encrypted_credentials)
    if changed:
        row.stores=[]
        row.selected_store_id=None
        row.tested_at=None
        row.test_error_code=None
    row.base_url=data.base_url
    row.encrypted_credentials=encrypt(credentials,context.company.id,data.base_url)
    row.version=data.version+1
    row.updated_at=now()
    audit(db,context.user,'gestaoclick.credentials_saved')
    db.commit()
    return output(db,context.company.id)

@router.post('/remove')
def remove(data: Version,context: Context=Depends(admin_context),db: Session=Depends(get_db)):
    db.execute(update(Company).where(Company.id==context.company.id).values(name=Company.name))
    row=db.get(Connection,context.company.id)
    if (row.version if row else 0)!=data.version:
        raise HTTPException(409,'A configuração foi atualizada. Recarregue antes de remover.')
    if row:
        row.stores=[]
        row.selected_store_id=None
        row.tested_at=None
        row.test_error_code=None
        row.last_test_started_at=None
        row.encrypted_credentials=None
        row.base_url=''
        row.version+=1
        row.updated_at=now()
        audit(db,context.user,'gestaoclick.credentials_removed')
        db.commit()
    return output(db,context.company.id)


class StoreSelection(Version):
    store_id: str=Field(pattern=r'^[0-9]{1,40}$')

def authorize_fresh(db,context):
    db.expire_all()
    user=db.get(User,context.user.id)
    company=db.get(Company,context.company.id)
    session=db.get(AuthSession,context.session.token_hash)
    if not user or not company or not session or user.company_id!=company.id or session.company_id!=company.id or session.user_id!=user.id or not user.active or user.role!='admin' or not company.active or session.revoked or session.expires_at<=now() or (company.plan=='trial' and company.trial_ends_at<=now()):
        raise HTTPException(403,'O acesso foi alterado. Entre novamente para continuar.')

@router.post('/test')
def test_access(data: Version,context: Context=Depends(admin_context),db: Session=Depends(get_db)):
    throttle(db,f'gestaoclick:test:{context.company.id}',10)
    db.execute(update(Company).where(Company.id==context.company.id).values(name=Company.name))
    row=db.get(Connection,context.company.id)
    if not row or not row.encrypted_credentials:
        raise HTTPException(409,'Cadastre as credenciais antes de testar o acesso.')
    if row.version!=data.version:
        raise HTTPException(409,'A configuração foi atualizada. Recarregue antes de testar.')
    if row.last_test_started_at is not None and now()-row.last_test_started_at<1:
        raise HTTPException(429,'Aguarde um segundo antes de testar novamente.',headers={'Retry-After':'1'})
    company_id=context.company.id
    row.last_test_started_at=now()
    credentials=decrypt(row.encrypted_credentials,company_id,row.base_url)
    url=row.base_url
    db.commit()  # No database write lock held during network I/O.
    error=None
    try:
        stores=list_stores(url,credentials)
    except ERPError as exc:
        error=exc
        stores=[]
    db.execute(update(Company).where(Company.id==company_id).values(name=Company.name))
    authorize_fresh(db,context)
    row=db.get(Connection,company_id)
    if not row or row.version!=data.version or not row.encrypted_credentials:
        db.rollback()
        raise HTTPException(409,'A configuração mudou durante o teste. Recarregue e tente novamente.')
    row.stores=stores
    row.selected_store_id=row.selected_store_id if any(store['id']==row.selected_store_id for store in stores) else None
    row.tested_at=now()
    row.test_error_code=error.code if error else None
    row.version+=1
    row.updated_at=now()
    audit(db,context.user,'gestaoclick.access_test_failed' if error else 'gestaoclick.access_tested')
    db.commit()
    if error:
        raise HTTPException(error.status,error.message,headers={'Retry-After':'1'} if error.status==429 else None)
    return output(db,company_id)

@router.post('/store')
def select_store(data: StoreSelection,context: Context=Depends(admin_context),db: Session=Depends(get_db)):
    db.execute(update(Company).where(Company.id==context.company.id).values(name=Company.name))
    row=db.get(Connection,context.company.id)
    if not row or not row.encrypted_credentials or row.test_error_code or row.tested_at is None or now()-row.tested_at>900:
        raise HTTPException(409,'Teste o acesso novamente antes de selecionar uma loja.')
    if row.version!=data.version:
        raise HTTPException(409,'A configuração mudou. Recarregue antes de selecionar a loja.')
    if not any(store['id']==data.store_id for store in row.stores):
        raise HTTPException(422,'A loja não consta na última consulta autorizada desta empresa.')
    row.selected_store_id=data.store_id
    row.version+=1
    row.updated_at=now()
    audit(db,context.user,'gestaoclick.store_selected')
    db.commit()
    return output(db,context.company.id)
