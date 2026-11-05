from fastapi import APIRouter, Depends, Request, Response, HTTPException
from sqlalchemy.orm import Session as DBSession
from sqlalchemy.exc import IntegrityError
from app.api.dependencies import current_context, admin_context, active_tenant, Context
from app.core.config import get_settings, Settings, COOKIE_NAME
from app.core.database import get_db
from app.core.security import now, throttle, passwords
from app.models.auth import User, Session
from app.schemas.auth import LoginInput, RegisterInput, UserInput, UserUpdate, UserOutput, IdentityOutput
from app.services import auth
from app.repositories.users import in_company
from app.schemas.company import CompanySettingsInput, CompanySettingsOutput
from app.services import company as company_service

router = APIRouter(prefix='/api/v1')

def identity(user, company):
    return {'user': user, 'company': company, 'trial_expired': company.plan == 'trial' and company.trial_ends_at <= now()}

def set_session(response, token, lifetime, remember, settings):
    response.set_cookie(COOKIE_NAME, token, max_age=lifetime if remember else None, httponly=True, secure=settings.cookie_secure, samesite='lax', path='/')

def limit_auth(request, db, email, action, limit):
    ip = request.client.host if request.client else 'unknown'
    throttle(db, f'{action}:ip:{ip}', limit * 5)
    throttle(db, f'{action}:email:{email}', limit)

@router.post('/auth/register', response_model=IdentityOutput, status_code=201)
def register(data: RegisterInput, request: Request, response: Response, db: DBSession = Depends(get_db), settings: Settings = Depends(get_settings)):
    limit_auth(request, db, data.email, 'register', 5)
    user, company, token, lifetime = auth.register(db, data, settings)
    set_session(response, token, lifetime, data.remember, settings)
    return identity(user, company)

@router.post('/auth/login', response_model=IdentityOutput)
def login(data: LoginInput, request: Request, response: Response, db: DBSession = Depends(get_db), settings: Settings = Depends(get_settings)):
    limit_auth(request, db, data.email, 'login', 10)
    user, company, token, lifetime = auth.login(db, data, settings)
    set_session(response, token, lifetime, data.remember, settings)
    return identity(user, company)

@router.get('/auth/me', response_model=IdentityOutput)
def me(context: Context = Depends(current_context)):
    return identity(context.user, context.company)

@router.post('/auth/logout', status_code=204)
def logout(response: Response, context: Context = Depends(current_context), db: DBSession = Depends(get_db), settings: Settings = Depends(get_settings)):
    context.session.revoked = True
    auth.audit(db, context.user, 'auth.logout')
    db.commit()
    response.delete_cookie(COOKIE_NAME, path='/', httponly=True, secure=settings.cookie_secure, samesite='lax')

@router.get('/users', response_model=list[UserOutput])
def list_users(context: Context = Depends(admin_context), db: DBSession = Depends(get_db)):
    return in_company(db, context.company.id)

@router.get('/users/{user_id}', response_model=UserOutput)
def get_user(user_id: str, context: Context = Depends(admin_context), db: DBSession = Depends(get_db)):
    user = in_company(db, context.company.id, user_id)
    if not user:
        raise HTTPException(404, 'Usuário não encontrado.')
    return user

@router.post('/users', response_model=UserOutput, status_code=201)
def create_user(data: UserInput, context: Context = Depends(admin_context), db: DBSession = Depends(get_db)):
    user = User(company_id=context.company.id, name=data.name, email=str(data.email), role=data.role, password_hash=passwords.hash(data.password))
    db.add(user)
    try:
        db.flush()
        auth.audit(db, context.user, 'user.created')
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'E-mail indisponível.')
    return user

@router.patch('/users/{user_id}', response_model=UserOutput)
def update_user(user_id: str, data: UserUpdate, context: Context = Depends(admin_context), db: DBSession = Depends(get_db)):
    user = in_company(db, context.company.id, user_id)
    if not user:
        raise HTTPException(404, 'Usuário não encontrado.')
    if user.id == context.user.id and (not data.active or data.role != 'admin'):
        raise HTTPException(409, 'Você não pode desativar ou remover seu próprio perfil de administrador.')
    revoke = user.role != data.role or user.email != str(data.email) or user.active != data.active
    user.name, user.email, user.role, user.active = data.name, str(data.email), data.role, data.active
    try:
        db.flush()
        if revoke:
            from sqlalchemy import update
            db.execute(update(Session).where(Session.user_id == user.id, Session.company_id == context.company.id).values(revoked=True))
        auth.audit(db, context.user, 'user.updated')
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'E-mail indisponível.')
    return user


@router.get('/company/settings', response_model=CompanySettingsOutput)
def company_settings(context: Context = Depends(active_tenant), db: DBSession = Depends(get_db)):
    return company_service.read_settings(db, context.company)

@router.patch('/company/settings', response_model=CompanySettingsOutput)
def save_company_settings(data: CompanySettingsInput, context: Context = Depends(admin_context), db: DBSession = Depends(get_db)):
    return company_service.save_settings(db, context, data)
