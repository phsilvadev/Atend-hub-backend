"""Private, self-hosted Baileys gateway. Never expose the gateway token to a browser."""
import re
import httpx
from fastapi import HTTPException
from app.core.config import get_settings

def configured():
    settings=get_settings()
    return bool(settings.whatsapp_qr_bridge_url and len(settings.whatsapp_qr_bridge_token.get_secret_value()) >= 32)

def gateway(method, session_id):
    if not configured():
        raise HTTPException(503,'A conexão por QR Code ainda não está disponível. Solicite a ativação ao suporte.')
    settings=get_settings()
    try:
        response=httpx.request(method,f'{settings.whatsapp_qr_bridge_url.rstrip("/")}/sessions/{session_id}',headers={'Authorization':'Bearer '+settings.whatsapp_qr_bridge_token.get_secret_value()},timeout=8,follow_redirects=False)
        response.raise_for_status()
        data=response.json()
        if not isinstance(data,dict) or data.get('status') not in {'disconnected','connecting','qr','connected','error'}:
            raise ValueError()
        qr=data.get('qr_data_url')
        if qr is not None and (not isinstance(qr,str) or len(qr)>100000 or not re.fullmatch(r'data:image/png;base64,[A-Za-z0-9+/=]+',qr)):
            raise ValueError()
        phone=data.get('phone')
        if phone is not None and (not isinstance(phone,str) or not re.fullmatch(r'\d{10,15}',phone)):
            raise ValueError()
        expiry=data.get('qr_expires_at')
        if expiry is not None and (not isinstance(expiry,int) or expiry<0):
            raise ValueError()
        return {key:data.get(key) for key in ('status','qr_data_url','qr_expires_at','phone')}
    except (httpx.HTTPError,ValueError,TypeError):
        raise HTTPException(503,'Não foi possível consultar a conexão do WhatsApp. Tente novamente.')
