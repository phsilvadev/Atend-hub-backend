import hashlib
import secrets
import time
from pwdlib import PasswordHash
from sqlalchemy import select, func, delete
from fastapi import HTTPException
from app.models.auth import AuthAttempt

passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash('not-a-real-user-password')

def now():
    return int(time.time())

def digest(value: str):
    return hashlib.sha256(value.encode()).hexdigest()

def new_token():
    return secrets.token_urlsafe(32)

def verify_password(password, encoded):
    try:
        return passwords.verify(password, encoded)
    except (ValueError, TypeError):
        return False

def throttle(db, key: str, limit: int):
    timestamp = now()
    hashed = digest(key)
    count = db.scalar(select(func.count()).select_from(AuthAttempt).where(AuthAttempt.key_hash == hashed, AuthAttempt.created_at > timestamp - 900))
    if count >= limit:
        raise HTTPException(429, 'Muitas tentativas. Aguarde 15 minutos.', headers={'Retry-After': '900'})
    db.execute(delete(AuthAttempt).where(AuthAttempt.created_at <= timestamp - 900))
    db.add(AuthAttempt(key_hash=hashed, created_at=timestamp))
    db.commit()
