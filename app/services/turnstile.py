"""Cloudflare Siteverify; challenge tokens never grant login by themselves."""
from datetime import datetime, timezone
import json
import httpx
from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from app.core.security import digest, now
from app.models.auth import ChallengeUse

SITEVERIFY = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'
TEST_SITE_KEY = '1x00000000000000000000AA'
TEST_SECRET_KEY = '1x0000000000000000000000000000000AA'

def configuration(settings):
    return {'enabled': settings.turnstile_enabled, 'site_key': settings.turnstile_site_key if settings.turnstile_enabled else None, 'testing': settings.turnstile_testing if settings.turnstile_enabled else False}

def verify(db, settings, token, action):
    if not settings.turnstile_enabled:
        if settings.app_env == 'production':
            raise HTTPException(503, 'A proteção de acesso não está configurada.')
        return
    raw = token.get_secret_value() if token else ''
    if not raw or not raw.strip() or len(raw) > 2048:
        raise HTTPException(403, 'Confirme a verificação de segurança antes de continuar.')
    testing = settings.turnstile_testing and settings.app_env != 'production' and settings.turnstile_site_key == TEST_SITE_KEY and settings.turnstile_secret_key.get_secret_value() == TEST_SECRET_KEY
    fingerprint = digest(raw)
    if not testing and db.get(ChallengeUse, fingerprint):
        raise HTTPException(403, 'Verificação já utilizada. Confirme novamente.')
    try:
        with httpx.Client(timeout=6, follow_redirects=False) as client:
            with client.stream('POST', SITEVERIFY, data={'secret': settings.turnstile_secret_key.get_secret_value(), 'response': raw}) as response:
                body = bytearray()
                for chunk in response.iter_bytes():
                    if len(body) + len(chunk) > 65536:
                        raise ValueError()
                    body.extend(chunk)
                if response.status_code != 200:
                    raise ValueError()
                result = json.loads(body)
    except (httpx.HTTPError, ValueError, TypeError):
        raise HTTPException(503, 'A verificação de segurança está indisponível. Aguarde e tente novamente.') from None
    if not isinstance(result, dict) or result.get('success') is not True:
        raise HTTPException(403, 'Verificação inválida ou expirada. Confirme novamente.')
    if not testing and (result.get('action') != action or result.get('hostname') not in settings.turnstile_allowed_hostnames):
        raise HTTPException(403, 'A verificação não corresponde a este formulário.')
    try:
        timestamp = datetime.fromisoformat(str(result['challenge_ts']).replace('Z', '+00:00'))
        age = datetime.now(timezone.utc).timestamp() - timestamp.timestamp()
        if timestamp.tzinfo is None or not -60 <= age <= 300:
            raise ValueError()
    except (KeyError, TypeError, ValueError, OverflowError):
        raise HTTPException(403, 'Verificação expirada. Confirme novamente.') from None
    if testing:
        return  # Official test tokens are constant; never allowed in production.
    # Atomic, persistent single-use guard, in addition to Siteverify's own protection.
    db.execute(delete(ChallengeUse).where(ChallengeUse.expires_at <= now()))
    db.add(ChallengeUse(token_hash=fingerprint, expires_at=now() + 360))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(403, 'Verificação já utilizada. Confirme novamente.') from None
