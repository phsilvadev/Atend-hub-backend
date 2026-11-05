"""Tenant configuration only. No external requests are performed by these routes."""
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
from app.core.security import now
from app.models.auth import Company
from app.models.gestaoclick import GestaoClickConnection as Connection
from app.schemas.auth import StrictInput
from app.services.auth import audit

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
    return {'company_id':company_id,'enabled':configured(),'base_url':row.base_url if row else '',
        'has_credentials':bool(row and row.encrypted_credentials),'status':'credentials_saved' if row and row.encrypted_credentials else 'not_configured',
        'version':row.version if row else 0,'updated_at':row.updated_at if row else None}

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
        row.encrypted_credentials=None
        row.base_url=''
        row.version+=1
        row.updated_at=now()
        audit(db,context.user,'gestaoclick.credentials_removed')
        db.commit()
    return output(db,context.company.id)
