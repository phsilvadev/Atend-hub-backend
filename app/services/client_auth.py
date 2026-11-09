"""Client identity verification and email transport. Never log credentials or reset URLs."""
import hmac
import re
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlsplit
from fastapi import HTTPException
from pydantic import TypeAdapter, EmailStr
from google.oauth2 import id_token
from google.auth.transport.requests import Request as GoogleRequest
from app.core.security import digest

class BoundedGoogleRequest(GoogleRequest):
    def __call__(self, *args, **kwargs):
        kwargs['timeout'] = 6
        return super().__call__(*args, **kwargs)

def verify_google(credential, client_id, nonce_hash):
    transport = BoundedGoogleRequest()
    try:
        claims = id_token.verify_oauth2_token(credential, transport, client_id)
        email = str(TypeAdapter(EmailStr).validate_python(claims.get('email', ''))).lower()
        subject = claims.get('sub')
        nonce = claims.get('nonce')
        if claims.get('email_verified') is not True or not isinstance(subject, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,255}', subject) or not isinstance(nonce, str) or not hmac.compare_digest(digest(nonce), nonce_hash):
            raise ValueError()
        authoritative = email.endswith('@gmail.com') or (bool(claims.get('hd')) and claims['hd'] == email.rsplit('@', 1)[-1])
        name = claims.get('name')
        name = name.strip()[:120] if isinstance(name, str) else ''
        return {'subject': subject, 'email': email, 'name': name if len(name) >= 2 else email.split('@')[0][:120], 'authoritative': authoritative}
    except Exception:
        raise HTTPException(401, 'Não foi possível validar sua conta Google. Inicie novamente.') from None
    finally:
        transport.session.close()

def recovery_configured(settings):
    parsed = urlsplit(settings.auth_public_origin)
    valid_origin = bool(parsed.hostname and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment and parsed.path in ('', '/') and settings.auth_public_origin.rstrip('/') in settings.allowed_origins)
    secure = parsed.scheme == 'https' or (settings.app_env != 'production' and parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost'))
    try: TypeAdapter(EmailStr).validate_python(settings.smtp_from)
    except ValueError: return False
    return bool(valid_origin and secure and settings.smtp_host and settings.smtp_username and settings.smtp_password.get_secret_value())

def send_reset_email(settings, email, token):
    message = EmailMessage()
    message['Subject'] = 'Redefina sua senha — AtendeHub'
    message['From'] = settings.smtp_from
    message['To'] = email
    url = settings.auth_public_origin.rstrip('/') + '/redefinir-senha#token=' + token
    message.set_content('Recebemos um pedido para redefinir sua senha do AtendeHub.\n\nAbra o link em até 15 minutos:\n' + url + '\n\nSe não foi você, ignore este e-mail. Sua senha continua a mesma. Não compartilhe este link.')
    try:
        # STARTTLS is mandatory; never send a password over plain SMTP.
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=8) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
            smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
            smtp.send_message(message)
    except Exception:
        raise HTTPException(503, 'Não foi possível enviar o e-mail agora. Tente mais tarde.') from None


def deliver_reset_email(settings, email, token):
    # Never reveal account existence or SMTP errors in the public reset response.
    try:
        send_reset_email(settings, email, token)
    except Exception:
        import logging
        logging.getLogger('atendehub').warning('password_reset_email_delivery_failed')
