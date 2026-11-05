import hashlib
import hmac
import json
import pytest
from sqlalchemy import select,func
from app.core.config import get_settings
from app.core.security import now
from app.models.auth import User
from app.models.whatsapp_qr import WhatsAppQRConnection
from app.models.conversations import Conversation, ConversationMessage
from app.api import whatsapp_qr as api

PREFIX='/api/v1/integrations/whatsapp-qr'
TOKEN='test-only-bridge-token-at-least-32-chars'

def configure(monkeypatch):
    monkeypatch.setenv('WHATSAPP_QR_BRIDGE_URL','http://127.0.0.1:8300')
    monkeypatch.setenv('WHATSAPP_QR_BRIDGE_TOKEN',TOKEN)
    get_settings.cache_clear()

def mock_gateway(monkeypatch):
    calls=[]
    def gateway(method,id):
        calls.append((method,id))
        return {'status':'disconnected' if method=='DELETE' else 'qr','qr_data_url':None if method=='DELETE' else 'data:image/png;base64,AA==','qr_expires_at':now()+40,'phone':None}
    monkeypatch.setattr(api,'gateway',gateway)
    return calls

def callback(client,session_id,external='qr-message',signature=None,timestamp=None):
    raw=json.dumps({'session_id':session_id,'external_id':external,'sender':'5511999999999','name':'Cliente QR','body':'Preciso de vergalhão','timestamp':now()}).encode()
    timestamp=str(timestamp or now())
    signature=signature or hmac.new(TOKEN.encode(),timestamp.encode()+b'.'+raw,hashlib.sha256).hexdigest()
    return client.post(api.QR_WEBHOOK_PATH,content=raw,headers={'Origin':'https://internal.example','x-bridge-timestamp':timestamp,'x-bridge-signature':signature})

def test_unconfigured_and_admin_only(client,database,signup,monkeypatch):
    monkeypatch.delenv('WHATSAPP_QR_BRIDGE_URL',raising=False);monkeypatch.delenv('WHATSAPP_QR_BRIDGE_TOKEN',raising=False);get_settings.cache_clear()
    assert client.get(PREFIX).status_code == 401
    identity=client.post('/api/v1/auth/register',json=signup).json()
    result=client.get(PREFIX).json();assert result['enabled'] is False and result['qr_data_url'] is None
    assert client.post(PREFIX+'/connect',json={}).status_code == 503
    with database() as db:
        user=db.get(User,identity['user']['id']);user.role='seller';db.commit()
    assert client.get(PREFIX).status_code == 403
    assert client.post(PREFIX+'/connect',json={}).status_code == 403


def test_tenant_routing_callback_replay_and_disconnect(client,database,signup,monkeypatch):
    configure(monkeypatch);calls=mock_gateway(monkeypatch)
    a=client.post('/api/v1/auth/register',json=signup).json()
    assert client.post(PREFIX+'/connect',json={'company_id':'forged'}).status_code==422
    assert client.post(PREFIX+'/connect',json={}).status_code==200
    assert client.post(PREFIX+'/connect',json={}).status_code==200
    session_a=calls[-1][1];assert calls[0][1] == session_a
    client.post('/api/v1/auth/logout',json={})
    b=client.post('/api/v1/auth/register',json={**signup,'email':'b@example.com','company':'Empresa B'}).json()
    assert client.get(PREFIX).json()['qr_data_url'] is None
    assert client.post(PREFIX+'/connect',json={}).status_code==200
    session_b=calls[-1][1];assert session_a != session_b
    assert callback(client,session_a,signature='bad').status_code==401
    assert callback(client,session_a,timestamp=now()-400).status_code==401
    assert callback(client,session_a).status_code==200
    assert callback(client,session_a).status_code==200
    assert client.get('/api/v1/conversations').json()['total']==0
    with database() as db:
        assert db.scalar(select(func.count()).select_from(ConversationMessage))==1
        conv=db.scalar(select(Conversation));assert conv.company_id==a['company']['id'] and conv.channel=='whatsapp_qr'
        conv.status='human';conv.assigned_user_id=a['user']['id'];db.commit()
    assert callback(client,session_a,external='second').status_code==200
    with database() as db:
        conv=db.scalar(select(Conversation));assert conv.status=='human' and conv.assigned_user_id==a['user']['id']
    client.post('/api/v1/auth/logout',json={})
    client.post('/api/v1/auth/login',json={'email':signup['email'],'password':signup['password']})
    assert client.get('/api/v1/conversations').json()['total']==1
    assert client.post(PREFIX+'/disconnect',json={}).status_code==200
    assert callback(client,session_a,external='late-message').status_code==200
    with database() as db:
        assert db.scalar(select(func.count()).select_from(ConversationMessage))==2
        assert db.get(WhatsAppQRConnection,a['company']['id']).active is False
    assert client.post(PREFIX+'/connect',json={}).status_code==200
    assert calls[-1][1] != session_a


def test_gateway_failure_never_claims_connected(client,database,signup,monkeypatch):
    from fastapi import HTTPException
    configure(monkeypatch)
    client.post('/api/v1/auth/register',json=signup)
    def fail(*args):raise HTTPException(503,'Serviço indisponível')
    monkeypatch.setattr(api,'gateway',fail)
    assert client.post(PREFIX+'/connect',json={}).status_code==503
    with database() as db:
        assert db.scalar(select(func.count()).select_from(WhatsAppQRConnection))==0


def test_gateway_contract_and_secret_is_server_only(monkeypatch):
    import httpx
    from app.integrations.whatsapp_qr import gateway
    from fastapi import HTTPException
    configure(monkeypatch)
    def response(method,url,**kwargs):
        assert kwargs['headers']['Authorization']=='Bearer '+TOKEN
        return httpx.Response(200,json={'status':'connected','phone':'5511999999999','qr_data_url':None,'qr_expires_at':None,'secret':'must-not-leak'},request=httpx.Request(method,url))
    monkeypatch.setattr(httpx,'request',response)
    result=gateway('GET','example');assert result['status']=='connected' and 'secret' not in result
    monkeypatch.setattr(httpx,'request',lambda method,url,**kwargs:httpx.Response(200,json={'status':'qr','qr_data_url':'https://attacker.example/qr.svg'},request=httpx.Request(method,url)))
    with pytest.raises(HTTPException):gateway('GET','example')
