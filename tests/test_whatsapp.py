import hashlib
import hmac
import json
from sqlalchemy import select, func
from app.core.config import get_settings
from app.core.security import now
from app.models.auth import Company
from app.models.conversations import Conversation, ConversationMessage, Customer
from app.models.whatsapp import WhatsAppNumber, WhatsAppReceipt

PATH='/api/v1/webhooks/whatsapp'

def configure(monkeypatch):
    monkeypatch.setenv('WHATSAPP_APP_SECRET','test-only-secret')
    monkeypatch.setenv('WHATSAPP_VERIFY_TOKEN','test-only-verify')
    get_settings.cache_clear()

def payload(phone='111',waba='222',external='wamid.test'):
    return {'object':'whatsapp_business_account','entry':[{'id':waba,'changes':[{'field':'messages','value':{'metadata':{'phone_number_id':phone},'contacts':[{'wa_id':'5511999999999','profile':{'name':'Cliente WhatsApp'}}],'messages':[{'from':'5511999999999','id':external,'timestamp':str(now()),'type':'text','text':{'body':'Tem metalon 30x30?'}}]}}]}]}

def post(client,data,signature=None):
    raw=json.dumps(data).encode()
    sig=signature or 'sha256='+hmac.new(b'test-only-secret',raw,hashlib.sha256).hexdigest()
    return client.post(PATH,content=raw,headers={'x-hub-signature-256':sig,'Origin':'https://meta.example'})

def seed(database):
    with database() as db:
        a=Company(name='A',trial_started_at=now(),trial_ends_at=now()+600)
        b=Company(name='B',trial_started_at=now(),trial_ends_at=now()+600)
        db.add_all([a,b]);db.flush()
        db.add_all([WhatsAppNumber(phone_number_id='111',waba_id='222',company_id=a.id),WhatsAppNumber(phone_number_id='333',waba_id='444',company_id=b.id)])
        db.commit()
        return a.id,b.id

def test_verification_and_signature(client,monkeypatch,database):
    assert client.get(PATH).status_code == 503
    configure(monkeypatch)
    assert client.get(PATH,params={'hub.mode':'subscribe','hub.verify_token':'test-only-verify','hub.challenge':'123'}).text == '123'
    assert client.get(PATH,params={'hub.mode':'subscribe','hub.verify_token':'bad','hub.challenge':'123'}).status_code == 403
    assert post(client,payload(),signature='sha256=invalid').status_code == 401
    assert client.post('/api/v1/conversations',json={},headers={'Origin':'https://meta.example'}).status_code == 403

def test_receive_deduplicate_isolate_and_reopen(client,monkeypatch,database):
    configure(monkeypatch)
    a,b=seed(database)
    assert post(client,payload()).status_code == 200
    assert post(client,payload()).status_code == 200
    assert post(client,payload('111','444','wrong-waba')).status_code == 200
    assert post(client,payload('unknown','222','unknown')).status_code == 200
    with database() as db:
        assert db.scalar(select(func.count()).select_from(ConversationMessage)) == 1
        assert db.scalar(select(func.count()).select_from(WhatsAppReceipt)) == 1
        conv=db.scalar(select(Conversation));assert conv.company_id == a and conv.channel == 'whatsapp'
        assert db.scalar(select(Customer)).phone == '5511999999999'
        conv.status='closed';db.commit()
    assert post(client,payload(external='second')).status_code == 200
    assert post(client,payload('333','444','wamid.test')).status_code == 200
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Conversation)) == 3
        assert db.scalar(select(func.count()).select_from(Customer)) == 2
        assert db.scalar(select(func.count()).select_from(ConversationMessage).where(ConversationMessage.company_id==b)) == 1

def test_disabled_tenant_and_unsupported_events(client,monkeypatch,database):
    configure(monkeypatch);a,_=seed(database)
    with database() as db:
        db.get(Company,a).active=False;db.commit()
    assert post(client,payload()).status_code == 200
    event=payload('333','444');event['entry'][0]['changes'][0]['value']['messages'][0]['type']='image'
    assert post(client,event).status_code == 200
    assert post(client,[]).status_code == 400
    with database() as db:
        assert db.scalar(select(func.count()).select_from(ConversationMessage)) == 0

def test_atomic_rollback_and_retry(client,monkeypatch,database):
    configure(monkeypatch);seed(database)
    event=payload()
    event['entry'].append({'id':'222','changes':[{'field':'messages','value':None}]})
    assert post(client,event).status_code == 400
    with database() as db:
        assert db.scalar(select(func.count()).select_from(ConversationMessage)) == 0
        assert db.scalar(select(func.count()).select_from(WhatsAppReceipt)) == 0
    assert post(client,payload()).status_code == 200


def test_concurrent_replay(database,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from app.services.whatsapp import receive
    configure(monkeypatch);seed(database)
    def process(_):
        with database() as db:
            receive(db,payload())
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(process,range(2)))
    with database() as db:
        assert db.scalar(select(func.count()).select_from(ConversationMessage)) == 1
        assert db.scalar(select(func.count()).select_from(Customer)) == 1

def test_cli_binding_is_idempotent_and_cannot_transfer(database,monkeypatch):
    import pytest
    from app.cli import whatsapp_number as cli
    a,b=seed(database)
    monkeypatch.setattr(cli,'SessionLocal',database)
    monkeypatch.setattr('sys.argv',['whatsapp_number','--company-id',a,'--phone-number-id','777','--waba-id','888'])
    cli.main();cli.main()
    with database() as db:
        assert db.get(WhatsAppNumber,'777').company_id == a
    monkeypatch.setattr('sys.argv',['whatsapp_number','--company-id',b,'--phone-number-id','777','--waba-id','888'])
    with pytest.raises(SystemExit):
        cli.main()
