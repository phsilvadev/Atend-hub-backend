import hashlib
import hmac
import json
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from app.core.config import get_settings
from app.core.database import get_db
from app.services.whatsapp import receive

WEBHOOK_PATH = '/api/v1/webhooks/whatsapp'
router = APIRouter(tags=['WhatsApp'])

@router.get(WEBHOOK_PATH)
def verify(request: Request):
    token = get_settings().whatsapp_verify_token.get_secret_value()
    query = request.query_params
    if not token:
        raise HTTPException(503, 'Webhook não configurado.')
    if query.get('hub.mode') != 'subscribe' or not hmac.compare_digest(query.get('hub.verify_token','').encode(), token.encode()):
        raise HTTPException(403, 'Verificação inválida.')
    challenge = query.get('hub.challenge','')
    if not challenge or len(challenge) > 200:
        raise HTTPException(400, 'Challenge inválido.')
    return PlainTextResponse(challenge)

@router.post(WEBHOOK_PATH)
async def webhook(request: Request, db: Session = Depends(get_db)):
    secret = get_settings().whatsapp_app_secret.get_secret_value()
    if not secret:
        raise HTTPException(503, 'Webhook não configurado.')
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 1024 * 1024:
            raise HTTPException(413, 'Evento muito grande.')
    signature = 'sha256=' + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(request.headers.get('x-hub-signature-256','').encode(),signature.encode()):
        raise HTTPException(401, 'Assinatura inválida.')
    try:
        payload = json.loads(raw)
        if not isinstance(payload,dict):
            raise ValueError()
        await run_in_threadpool(receive,db,payload)
    except (ValueError,TypeError,AttributeError):
        db.rollback()
        raise HTTPException(400, 'Evento inválido.')
    return {'status':'ok'}
