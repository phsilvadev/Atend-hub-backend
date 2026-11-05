import base64
import pytest
from sqlalchemy import select
from fastapi import HTTPException
from app.core.config import get_settings
from app.models.auth import User
from app.models.gestaoclick import GestaoClickConnection
from app.api.gestaoclick import decrypt

PATH='/api/v1/integrations/gestaoclick'
ACCESS='test-only-access-token'
SECRET='test-only-secret-token'
DATA={'version':0,'base_url':'https://erp.example.com/api/','access_token':ACCESS,'secret_access_token':SECRET}

def configure(monkeypatch):
    monkeypatch.setenv('WHATSAPP_CREDENTIAL_KEY',base64.urlsafe_b64encode(b'g'*32).decode());get_settings.cache_clear()

def test_encrypted_save_edit_and_remove(client,database,signup,monkeypatch):
    configure(monkeypatch)
    identity=client.post('/api/v1/auth/register',json=signup).json()
    response=client.post(PATH,json=DATA)
    assert response.status_code==200
    assert response.json()['status']=='credentials_saved' and response.json()['base_url']=='https://erp.example.com/api'
    assert ACCESS not in response.text and SECRET not in response.text and 'encrypted_credentials' not in response.text
    with database() as db:
        row=db.get(GestaoClickConnection,identity['company']['id'])
        assert ACCESS not in row.encrypted_credentials and SECRET not in row.encrypted_credentials
        assert decrypt(row.encrypted_credentials,row.company_id,row.base_url)['access_token']==ACCESS
        with pytest.raises(HTTPException):decrypt(row.encrypted_credentials,'other-tenant',row.base_url)
        with pytest.raises(HTTPException):decrypt(row.encrypted_credentials,row.company_id,'https://other.example/api')
    assert client.post(PATH,json={'base_url':'https://erp.example.com/api','version':1}).status_code==200
    assert client.post(PATH,json=DATA).status_code==409
    assert client.post(PATH,json={'base_url':'https://new.example.com/api','version':2}).status_code==422
    edited=client.post(PATH,json={'base_url':'https://erp.example.com/api','version':2,'secret_access_token':'replacement-test-secret'})
    assert edited.status_code==200
    with database() as db:
        row=db.get(GestaoClickConnection,identity['company']['id']);values=decrypt(row.encrypted_credentials,row.company_id,row.base_url)
        assert values['access_token']==ACCESS and values['secret_access_token']=='replacement-test-secret'
    assert client.post(PATH+'/remove',json={'version':2}).status_code==409
    assert client.post(PATH+'/remove',json={'version':3}).json()['status']=='not_configured'
    with database() as db:
        row=db.get(GestaoClickConnection,identity['company']['id']);assert row.encrypted_credentials is None and row.base_url==''


def test_permissions_and_tenant_isolation(client,database,signup,monkeypatch):
    configure(monkeypatch)
    assert client.get(PATH).status_code==401
    a=client.post('/api/v1/auth/register',json=signup).json()
    assert client.post(PATH,json={**DATA,'company_id':'forged'}).status_code==422
    assert client.post(PATH,json=DATA).status_code==200
    client.post('/api/v1/auth/logout',json={})
    b=client.post('/api/v1/auth/register',json={**signup,'email':'b@example.com','company':'Empresa B'}).json()
    assert not client.get(PATH).json()['has_credentials']
    assert client.post(PATH+'/remove',json={'version':0}).status_code==200
    with database() as db:
        assert db.get(GestaoClickConnection,a['company']['id']).encrypted_credentials
        db.get(User,b['user']['id']).role='seller';db.commit()
    assert client.get(PATH).status_code==403
    assert client.post(PATH,json=DATA).status_code==403
    assert client.post(PATH+'/remove',json={'version':0}).status_code==403


def test_invalid_urls_and_missing_encryption_key(client,database,signup,monkeypatch):
    configure(monkeypatch)
    client.post('/api/v1/auth/register',json=signup)
    for url in ['http://erp.example.com/api','https://user:pass@erp.example.com/api','https://127.0.0.1/api','https://localhost/api','https://erp.internal/api','https://erp.example.com/api?token=secret','https://erp.example.com/api/clientes']:
        assert client.post(PATH,json={**DATA,'base_url':url}).status_code==422
    monkeypatch.setenv('WHATSAPP_CREDENTIAL_KEY','');get_settings.cache_clear()
    assert client.get(PATH).json()['enabled'] is False
    assert client.post(PATH,json=DATA).status_code==503
    with database() as db:
        assert db.scalar(select(GestaoClickConnection)) is None
