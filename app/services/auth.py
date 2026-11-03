from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from app.core.security import now, new_token, digest, passwords, verify_password, DUMMY_HASH
from app.models.auth import Company, User, Session, AuditEvent
from app.repositories.users import by_email

TRIAL_SECONDS = 7 * 24 * 60 * 60

def audit(db, user, action):
    db.add(AuditEvent(company_id=user.company_id, actor_id=user.id, action=action, created_at=now()))

def issue_session(db, user, remember, settings):
    token = new_token()
    lifetime = settings.remember_days * 86400 if remember else settings.session_hours * 3600
    db.add(Session(token_hash=digest(token), user_id=user.id, company_id=user.company_id, expires_at=now() + lifetime))
    return token, lifetime

def register(db, data, settings):
    timestamp = now()
    company = Company(name=data.company, trial_started_at=timestamp, trial_ends_at=timestamp + TRIAL_SECONDS)
    db.add(company)
    db.flush()
    user = User(company_id=company.id, name=data.name, email=str(data.email), password_hash=passwords.hash(data.password), role='admin')
    db.add(user)
    try:
        db.flush()
        token, lifetime = issue_session(db, user, data.remember, settings)
        audit(db, user, 'company.registered')
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Não foi possível cadastrar este e-mail. Use outro ou entre na sua conta.')
    return user, company, token, lifetime

def login(db, data, settings):
    user = by_email(db, data.email)
    valid = verify_password(data.password, user.password_hash if user else DUMMY_HASH)
    company = db.get(Company, user.company_id) if user else None
    if not valid or not user or not user.active or not company or not company.active:
        raise HTTPException(401, 'E-mail ou senha inválidos.')
    token, lifetime = issue_session(db, user, data.remember, settings)
    audit(db, user, 'auth.login')
    db.commit()
    return user, company, token, lifetime
