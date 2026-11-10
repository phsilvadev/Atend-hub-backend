"""Platform-only administration. Secrets and privilege decisions stay on the server."""
import base64
import os
import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException
from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError
from app.models.knowledge import PlatformAdmin, PlatformSession, PlatformControl, PlatformOpenAI
from app.core.config import get_settings
from app.core.security import now, passwords, verify_password, throttle
from app.services.platform_auth import audit


def control(db):
    value=db.get(PlatformControl,1)
    if not value or not value.primary_admin_id:
        raise HTTPException(503,'A identidade primária da plataforma precisa ser provisionada.')
    return value


def primary(db,actor):
    return control(db).primary_admin_id==actor.id


def output(db,admin,actor):
    protected=control(db).primary_admin_id==admin.id
    return {'id':admin.id,'name':admin.name,'email':admin.email,'active':admin.active,'version':admin.version,
            'is_primary':protected,'is_self':admin.id==actor.id,'can_edit':not protected or admin.id==actor.id,
            'can_deactivate':not protected and admin.id!=actor.id}


def reauthenticate(db,context,password):
    # This bucket is persisted before validation; repeated wrong confirmations remain limited.
    throttle(db,f'platform.sensitive:{context.admin.id}',30)
    gate=control(db)
    locked=db.execute(update(PlatformControl).where(PlatformControl.id==1,PlatformControl.version==gate.version).values(version=PlatformControl.version+1))
    if locked.rowcount!=1:
        db.rollback();raise HTTPException(409,'Outra operação administrativa está em andamento. Atualize e tente novamente.')
    db.refresh(context.admin);db.refresh(context.session)
    if not context.admin.active or context.session.revoked or context.session.expires_at<=now():
        raise HTTPException(401,'Acesso de plataforma necessário.')
    if not verify_password(password.get_secret_value(),context.admin.password_hash):
        raise HTTPException(403,'Confirme sua senha atual para continuar.')


def create_admin(db,context,data):
    reauthenticate(db,context,data.current_password)
    row=PlatformAdmin(name=data.name,email=str(data.email),password_hash=passwords.hash(data.password.get_secret_value()),active=True,version=1)
    db.add(row)
    try:
        db.flush();audit(db,context.admin,'platform.admin.created',row.id);db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Este e-mail já está cadastrado.') from None
    return output(db,row,context.admin)


def edit_admin(db,context,admin_id,data):
    reauthenticate(db,context,data.current_password)
    row=db.get(PlatformAdmin,str(admin_id))
    if not row: raise HTTPException(404,'Administrador não encontrado.')
    if row.id==control(db).primary_admin_id and row.id!=context.admin.id:
        raise HTTPException(403,'O primeiro superadministrador só pode ser alterado pela própria conta.')
    if not data.active and (row.id==control(db).primary_admin_id or row.id==context.admin.id):
        raise HTTPException(403,'Não é permitido desativar o primeiro administrador ou sua própria conta.')
    if row.version!=data.version:
        raise HTTPException(409,'Administrador atualizado por outra pessoa. Recarregue a listagem.')
    if not data.active and db.scalar(select(func.count()).select_from(PlatformAdmin).where(PlatformAdmin.active.is_(True)))<=1:
        raise HTTPException(409,'É necessário manter ao menos um administrador ativo.')
    old_email=row.email
    row.name=data.name;row.email=str(data.email);row.active=data.active;row.version+=1
    if data.password: row.password_hash=passwords.hash(data.password.get_secret_value())
    if data.password or not row.active or old_email!=row.email:
        db.execute(update(PlatformSession).where(PlatformSession.admin_id==row.id).values(revoked=True))
    try:
        audit(db,context.admin,'platform.admin.updated',row.id);db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Este e-mail já está cadastrado.') from None
    return {**output(db,row,context.admin),'requires_login':row.id==context.admin.id and (bool(data.password) or old_email!=row.email)}


def secret_key():
    try:
        key=base64.b64decode(get_settings().platform_credential_key.get_secret_value(),altchars=b'-_',validate=True)
        if len(key)!=32: raise ValueError()
        return key
    except (ValueError,TypeError):
        raise HTTPException(503,'Configure PLATFORM_CREDENTIAL_KEY no ambiente protegido do backend.') from None


def storage_ready():
    try: secret_key();return True
    except HTTPException: return False


def encrypt(value):
    nonce=os.urandom(12)
    return 'v1:'+base64.urlsafe_b64encode(nonce+AESGCM(secret_key()).encrypt(nonce,value.encode(),b'atendehub:platform:openai:v1')).decode()


def decrypt(value):
    try:
        if not value.startswith('v1:'):raise ValueError()
        raw=base64.b64decode(value[3:],altchars=b'-_',validate=True)
        return AESGCM(secret_key()).decrypt(raw[:12],raw[12:],b'atendehub:platform:openai:v1').decode()
    except HTTPException: raise
    except Exception:
        raise HTTPException(503,'Não foi possível acessar a chave protegida. Revise o armazenamento do servidor.') from None


def config_output(db,actor):
    row=db.get(PlatformOpenAI,1)
    return {'model':row.model,'version':row.version,'configured':bool(row.key_ciphertext),'storage_ready':storage_ready(),
            'checked_at':row.checked_at,'check_status':row.check_status,'can_manage':True,
            'diagnostic_only':True}


def config_auth(db,context,password):
    reauthenticate(db,context,password)


def save_config(db,context,data):
    config_auth(db,context,data.current_password)
    row=db.get(PlatformOpenAI,1)
    if row.version!=data.version:raise HTTPException(409,'Configuração atualizada. Recarregue antes de salvar.')
    if not data.api_key and not row.key_ciphertext:raise HTTPException(422,'Informe a chave OpenAI.')
    if data.api_key:row.key_ciphertext=encrypt(data.api_key.get_secret_value())
    row.model=data.model;row.version+=1;row.checked_at=None;row.check_status=None
    audit(db,context.admin,'platform.openai.updated');db.commit()
    return config_output(db,context.admin)


def remove_config(db,context,data):
    config_auth(db,context,data.current_password)
    row=db.get(PlatformOpenAI,1)
    if row.version!=data.version:raise HTTPException(409,'Configuração atualizada. Recarregue antes de remover.')
    row.key_ciphertext=None;row.version+=1;row.checked_at=None;row.check_status=None
    audit(db,context.admin,'platform.openai.removed');db.commit()
    return config_output(db,context.admin)


def probe_model(key,model):
    # Fixed official host; no configurable URL, redirects, inference or customer data.
    try:
        with httpx.Client(timeout=10,follow_redirects=False) as client:
            response=client.get(f'https://api.openai.com/v1/models/{model}',headers={'Authorization':f'Bearer {key}'})
        if response.status_code==200:
            body=response.json()
            return 'verified' if isinstance(body,dict) and body.get('id')==model else 'unavailable'
        return {401:'invalid_key',403:'forbidden',404:'model_unavailable',429:'rate_limited'}.get(response.status_code,'unavailable')
    except (httpx.HTTPError,ValueError):return 'unavailable'


def test_config(db,context,data):
    config_auth(db,context,data.current_password)
    throttle(db,'platform.openai.diagnostics',10)
    row=db.get(PlatformOpenAI,1)
    if row.version!=data.version:raise HTTPException(409,'Configuração atualizada. Recarregue antes de testar.')
    if not row.key_ciphertext:raise HTTPException(422,'Cadastre a chave antes de testar.')
    key=decrypt(row.key_ciphertext);model=row.model;version=row.version
    db.commit()  # Do not hold the administrative lock across a provider request.
    status=probe_model(key,model)
    # Revalidate account/session and acquire the common lock after the request.
    config_auth(db,context,data.current_password)
    changed=db.execute(update(PlatformOpenAI).where(PlatformOpenAI.id==1,PlatformOpenAI.version==version).values(check_status=status,checked_at=now(),version=PlatformOpenAI.version+1))
    if changed.rowcount!=1:
        db.rollback();raise HTTPException(409,'A configuração mudou durante o teste. Execute um novo teste.')
    audit(db,context.admin,'platform.openai.tested');db.commit()
    db.expire_all()
    return config_output(db,context.admin)
