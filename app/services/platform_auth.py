from dataclasses import dataclass
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select, update
from app.core.database import get_db
from app.core.security import now, passwords, verify_password, DUMMY_HASH, new_token, digest
from app.models.knowledge import PlatformAdmin, PlatformSession, PlatformAudit, PlatformControl

PLATFORM_COOKIE='atendehub_platform_session'
LIFETIME=3600

@dataclass
class PlatformContext:
    admin: PlatformAdmin
    session: PlatformSession

def platform_context(request:Request,db=Depends(get_db)):
    token=request.cookies.get(PLATFORM_COOKIE)
    session=db.get(PlatformSession,digest(token)) if token and len(token)<256 else None
    admin=db.get(PlatformAdmin,session.admin_id) if session else None
    if not session or session.revoked or session.expires_at <= now() or not admin or not admin.active:
        raise HTTPException(401,'Acesso de plataforma necessário.')
    return PlatformContext(admin,session)

def audit(db,admin,action,target_id=None):
    db.add(PlatformAudit(admin_id=admin.id,action=action,target_id=target_id,created_at=now()))

def bootstrap(db,name,email,password):
    if len(password)<12 or len(password)>128 or not 2 <= len(name.strip()) <= 120:
        raise ValueError('Nome válido e senha de 12 a 128 caracteres são obrigatórios.')
    from pydantic import EmailStr, TypeAdapter
    email=str(TypeAdapter(EmailStr).validate_python(email.strip().lower()))
    if db.scalar(select(PlatformAdmin).where(PlatformAdmin.email == email)):
        raise ValueError('Administrador já cadastrado; nenhuma senha foi alterada.')
    admin=PlatformAdmin(name=name.strip(),email=email,password_hash=passwords.hash(password))
    db.add(admin);db.flush()
    db.execute(update(PlatformControl).where(PlatformControl.id==1,PlatformControl.primary_admin_id.is_(None)).values(primary_admin_id=admin.id,version=PlatformControl.version+1))
    audit(db,admin,'platform.admin.created');db.commit()
    return admin

def login(db,data):
    admin=db.scalar(select(PlatformAdmin).where(PlatformAdmin.email == str(data.email)))
    valid=verify_password(data.password,admin.password_hash if admin else DUMMY_HASH)
    if not valid or not admin or not admin.active:
        raise HTTPException(401,'E-mail ou senha inválidos.')
    result=db.execute(update(PlatformAdmin).where(PlatformAdmin.id==admin.id,PlatformAdmin.active.is_(True),PlatformAdmin.password_hash==admin.password_hash).values(password_hash=admin.password_hash))
    if result.rowcount!=1:
        db.rollback();raise HTTPException(401,'E-mail ou senha inválidos.')
    token=new_token()
    db.add(PlatformSession(token_hash=digest(token),admin_id=admin.id,expires_at=now()+LIFETIME))
    audit(db,admin,'platform.login');db.commit()
    return admin,token
