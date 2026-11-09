import hmac
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request, Response, BackgroundTasks
from pydantic import Field, SecretStr, field_validator
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession
from app.api.routes import limit_auth, identity, set_session
from app.core.config import get_settings, Settings
from app.core.database import get_db
from app.core.security import now, new_token, digest, passwords
from app.models.auth import GoogleIdentity, GoogleAuthFlow, PasswordReset, User, Company, Session
from app.schemas.auth import StrictInput, LoginInput, IdentityOutput, UserInput
from app.services import auth, turnstile, client_auth
from app.repositories.users import by_email

router = APIRouter(prefix='/api/v1/auth', tags=['Client access'])
FLOW_COOKIE = 'atendehub_google_flow'

class GoogleStart(StrictInput):
    mode: Literal['login', 'register']

class GoogleFinish(StrictInput):
    state: SecretStr = Field(min_length=40, max_length=100)
    credential: SecretStr = Field(min_length=100, max_length=8192)
    company: str = Field(default='', max_length=160)
    remember: bool = False
    challenge_token: SecretStr | None = Field(default=None, min_length=1, max_length=2048)

class Forgot(StrictInput):
    email: str = Field(max_length=254)
    challenge_token: SecretStr | None = Field(default=None, min_length=1, max_length=2048)
    @field_validator('email')
    @classmethod
    def email_format(cls, value):
        from pydantic import TypeAdapter, EmailStr
        return str(TypeAdapter(EmailStr).validate_python(value.strip().lower()))

class Reset(StrictInput):
    token: SecretStr = Field(min_length=40, max_length=100)
    password: str = Field(min_length=8, max_length=128)

@router.get('/options')
def options(settings: Settings = Depends(get_settings)):
    return {'google_enabled': bool(settings.google_auth_client_id), 'password_reset_enabled': client_auth.recovery_configured(settings)}

@router.post('/google/start')
def google_start(data: GoogleStart, request: Request, response: Response, db: DBSession = Depends(get_db), settings: Settings = Depends(get_settings)):
    if not settings.google_auth_client_id:
        raise HTTPException(503, 'O acesso pelo Google ainda não foi configurado pela plataforma.')
    limit_auth(request, db, request.client.host if request.client else 'unknown', 'google-start', 20)
    state, nonce, browser = new_token(), new_token(), new_token()
    db.execute(delete(GoogleAuthFlow).where(GoogleAuthFlow.expires_at < now()-86400))
    db.add(GoogleAuthFlow(state_hash=digest(state), browser_hash=digest(browser), nonce_hash=digest(nonce), mode=data.mode, expires_at=now()+300, consumed=False))
    db.commit()
    response.set_cookie(FLOW_COOKIE, browser, httponly=True, secure=settings.cookie_secure, samesite='lax', path='/api/v1/auth/google', max_age=300)
    return {'state': state, 'nonce': nonce, 'client_id': settings.google_auth_client_id}

@router.post('/google/complete', response_model=IdentityOutput)
def google_complete(data: GoogleFinish, request: Request, response: Response, db: DBSession = Depends(get_db), settings: Settings = Depends(get_settings)):
    if not settings.google_auth_client_id: raise HTTPException(503, 'Acesso Google indisponível.')
    limit_auth(request, db, request.client.host if request.client else 'unknown', 'google-complete', 20)
    flow = db.get(GoogleAuthFlow, digest(data.state.get_secret_value()))
    browser = request.cookies.get(FLOW_COOKIE, '')
    if not flow or not browser or len(browser) > 100 or flow.consumed or flow.expires_at <= now() or not hmac.compare_digest(flow.browser_hash, digest(browser)):
        raise HTTPException(409, 'Autorização expirada ou inválida. Inicie novamente.')
    if flow.mode == 'register' and len(data.company.strip()) < 2:
        raise HTTPException(422, 'Informe o nome da empresa para criar sua conta com Google.')
    mode, nonce_hash = flow.mode, flow.nonce_hash
    claimed = db.execute(update(GoogleAuthFlow).where(GoogleAuthFlow.state_hash == flow.state_hash, GoogleAuthFlow.consumed.is_(False), GoogleAuthFlow.expires_at > now()).values(consumed=True))
    db.commit()
    if claimed.rowcount != 1: raise HTTPException(409, 'Autorização já utilizada.')
    turnstile.verify(db, settings, data.challenge_token, 'client_register' if mode == 'register' else 'client_login')
    verified = client_auth.verify_google(data.credential.get_secret_value(), settings.google_auth_client_id, nonce_hash)
    linked = db.get(GoogleIdentity, verified['subject'])
    user = db.get(User, linked.user_id) if linked else None
    try:
        if not user:
            existing = by_email(db, verified['email'])
            if mode == 'login':
                # Only Google-authoritative Gmail/Workspace emails can link existing accounts.
                if not existing or not verified['authoritative']:
                    raise HTTPException(409, 'Esta conta Google ainda não está vinculada. Entre com e-mail e senha ou crie sua conta.')
                user = existing
            else:
                if existing: raise HTTPException(409, 'Este e-mail já possui uma conta. Entre para continuar.')
                timestamp = now()
                company = Company(name=data.company.strip(), plan='trial', trial_started_at=timestamp, trial_ends_at=timestamp+auth.TRIAL_SECONDS)
                db.add(company); db.flush()
                user = User(company_id=company.id, name=verified['name'], email=verified['email'], role='admin', password_hash=passwords.hash(new_token()))
                db.add(user); db.flush()
                auth.audit(db, user, 'company.registered_google')
            db.add(GoogleIdentity(subject=verified['subject'], user_id=user.id))
        company = db.get(Company, user.company_id)
        if not user.active or not company or not company.active: raise HTTPException(401, 'Conta indisponível. Procure o administrador.')
        token, lifetime = auth.issue_session(db, user, data.remember, settings)
        auth.audit(db, user, 'auth.login_google'); db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, 'Não foi possível vincular esta conta. Entre novamente.')
    set_session(response, token, lifetime, data.remember, settings)
    response.delete_cookie(FLOW_COOKIE, path='/api/v1/auth/google', httponly=True, secure=settings.cookie_secure, samesite='lax')
    return identity(user, company)

@router.post('/password/forgot', status_code=202)
def forgot(data: Forgot, request: Request, tasks: BackgroundTasks, db: DBSession = Depends(get_db), settings: Settings = Depends(get_settings)):
    if not client_auth.recovery_configured(settings): raise HTTPException(503, 'O envio de e-mails de recuperação ainda não foi configurado. Procure o administrador.')
    limit_auth(request, db, data.email, 'password-forgot', 5)
    turnstile.verify(db, settings, data.challenge_token, 'client_password_reset')
    user = by_email(db, data.email)
    company = db.get(Company, user.company_id) if user else None
    if user and user.active and company and company.active:
        raw = new_token()
        db.execute(delete(PasswordReset).where(PasswordReset.expires_at < now()-86400))
        db.execute(update(PasswordReset).where(PasswordReset.user_id == user.id).values(consumed=True))
        db.add(PasswordReset(token_hash=digest(raw), user_id=user.id, password_version=digest(user.password_hash), expires_at=now()+900, consumed=False))
        db.flush()
        auth.audit(db, user, 'auth.password_reset_requested'); db.commit()
        tasks.add_task(client_auth.deliver_reset_email, settings, user.email, raw)
    return {'message': 'Se houver uma conta elegível com esse e-mail, enviaremos as instruções para redefinir sua senha.'}

@router.post('/password/reset')
def reset(data: Reset, request: Request, response: Response, db: DBSession = Depends(get_db), settings: Settings = Depends(get_settings)):
    limit_auth(request, db, request.client.host if request.client else 'unknown', 'password-reset', 20)
    row = db.get(PasswordReset, digest(data.token.get_secret_value()))
    user = db.get(User, row.user_id) if row else None
    company = db.get(Company, user.company_id) if user else None
    if not row or row.consumed or row.expires_at <= now() or not user or not user.active or not company or not company.active or not hmac.compare_digest(row.password_version, digest(user.password_hash)):
        raise HTTPException(400, 'Link inválido, expirado ou já utilizado. Solicite um novo link.')
    claimed = db.execute(update(PasswordReset).where(PasswordReset.token_hash == row.token_hash, PasswordReset.consumed.is_(False), PasswordReset.expires_at > now()).values(consumed=True))
    if claimed.rowcount != 1: db.rollback(); raise HTTPException(400, 'Link já utilizado.')
    changed = db.execute(update(User).where(User.id == user.id, User.password_hash == user.password_hash).values(password_hash=passwords.hash(data.password)))
    if changed.rowcount != 1: db.rollback(); raise HTTPException(400, 'Link inválido. Solicite novamente.')
    db.execute(update(PasswordReset).where(PasswordReset.user_id == user.id).values(consumed=True))
    db.execute(update(Session).where(Session.user_id == user.id, Session.company_id == user.company_id).values(revoked=True))
    auth.audit(db, user, 'auth.password_reset_completed'); db.commit()
    return {'message': 'Senha atualizada. Entre novamente com sua nova senha.'}
