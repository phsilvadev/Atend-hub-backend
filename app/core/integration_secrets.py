"""AES-256-GCM; the master key belongs in the server's secret manager, never in SQL."""
import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException
from app.core.config import get_settings

def key_bytes():
    raw=get_settings().whatsapp_credential_key.get_secret_value()
    try:
        key=base64.b64decode(raw,altchars=b'-_',validate=True)
        if len(key)!=32:
            raise ValueError()
        return key
    except (ValueError,TypeError):
        raise HTTPException(503,'O armazenamento seguro de credenciais precisa ser ativado pela plataforma.')

def configured():
    try:
        key_bytes()
        return True
    except HTTPException:
        return False

def context(company_id,phone_id,waba_id):
    return f'atendehub:whatsapp:v1:{company_id}:{phone_id}:{waba_id}'.encode()

def encrypt_token(token,company_id,phone_id,waba_id):
    nonce=os.urandom(12)
    ciphertext=AESGCM(key_bytes()).encrypt(nonce,token.encode(),context(company_id,phone_id,waba_id))
    return 'v1:'+base64.urlsafe_b64encode(nonce+ciphertext).decode()

def decrypt_token(ciphertext,company_id,phone_id,waba_id):
    try:
        if not ciphertext.startswith('v1:'):
            raise ValueError()
        raw=base64.b64decode(ciphertext[3:],altchars=b'-_',validate=True)
        return AESGCM(key_bytes()).decrypt(raw[:12],raw[12:],context(company_id,phone_id,waba_id)).decode()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503,'Não foi possível acessar a credencial protegida. Solicite a revisão da chave da plataforma.')
