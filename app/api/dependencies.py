from dataclasses import dataclass
from fastapi import Depends, Request, HTTPException
from sqlalchemy.orm import Session as DBSession
from app.core.database import get_db
from app.core.config import COOKIE_NAME
from app.core.security import digest, now
from app.models.auth import Session, Company, User

@dataclass
class Context:
    user: User
    company: Company
    session: Session

def current_context(request: Request, db: DBSession = Depends(get_db)):
    token = request.cookies.get(COOKIE_NAME)
    session = db.get(Session, digest(token)) if token and len(token) < 256 else None
    if not session or session.revoked or session.expires_at <= now():
        raise HTTPException(401, 'Sessão inválida ou expirada.')
    user = db.get(User, session.user_id)
    company = db.get(Company, session.company_id)
    if not user or not company or not user.active or not company.active or user.company_id != company.id:
        raise HTTPException(401, 'Sessão inválida ou expirada.')
    return Context(user, company, session)

def active_tenant(context: Context = Depends(current_context)):
    if context.company.plan == 'trial' and context.company.trial_ends_at <= now():
        raise HTTPException(403, {'code': 'trial_expired', 'message': 'Seu período de teste terminou.'})
    return context

def admin_context(context: Context = Depends(active_tenant)):
    if context.user.role != 'admin':
        raise HTTPException(403, 'Acesso permitido apenas para administradores.')
    return context
