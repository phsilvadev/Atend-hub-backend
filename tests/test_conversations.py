from uuid import uuid4
import pytest
from sqlalchemy import select, func
from app.models.auth import Company, User, AuditEvent
from app.models.conversations import Customer, Conversation, ConversationMessage
from app.core.config import COOKIE_NAME
from app.core.security import now
from tests.test_auth import register

URL = '/api/v1/conversations'
def payload(**overrides):
    return {'request_id':str(uuid4()), 'customer_name':'Carlos Mendes', 'customer_phone':'(11) 99999-0101', 'customer_business':'Construtora Vale', 'subject':'Metalon 30x30 chapa 18', 'initial_message':'Preciso de 20 barras de 6 m.', **overrides}

def create(client, **overrides):
    response = client.post(URL, json=payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()

def test_create_persist_customer_dedup_history_and_search(client, signup, database):
    identity = register(client, signup)
    first = create(client, assigned_user_id=identity['user']['id'])
    assert first['company_id'] == identity['company']['id'] and first['channel'] == 'manual'
    assert first['status'] == 'human' and first['version'] == 1
    second = create(client, customer_phone='5511999990101', customer_name='Outro nome')
    assert second['customer']['id'] == first['customer']['id']
    assert second['customer']['name'] == 'Carlos Mendes'
    assert client.get(URL, params={'q':'chapa 18'}).json()['total'] == 2
    assert client.get(URL, params={'q':'(11) 99999-0101'}).json()['total'] == 2
    assert client.get(URL, params={'q':'inexistente'}).json()['total'] == 0
    assert client.get(URL, params={'q':'%'}).json()['total'] == 0
    assert client.get(URL, params={'mine':True}).json()['total'] == 1
    assert len(client.get(URL, params={'limit':1}).json()['items']) == 1
    history = client.get(f"{URL}/{first['id']}/messages").json()
    assert [m['kind'] for m in history['items']] == ['system','customer_record']
    assert 'Preciso de 20' in history['items'][1]['body']
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Customer)) == 1
        assert db.scalar(select(func.count()).select_from(Conversation)) == 2
        assert db.scalar(select(AuditEvent).where(AuditEvent.action == 'conversation.created'))

def test_create_idempotent_and_input_tampering(client, signup):
    register(client, signup)
    data = payload()
    first = client.post(URL, json=data).json()
    assert client.post(URL, json=data).json()['id'] == first['id']
    assert client.post(URL, json={**data,'subject':'Mudou'}).status_code == 409
    for extra in [{'company_id':str(uuid4())}, {'channel':'whatsapp'}, {'status':'ai'}]:
        assert client.post(URL,json={**payload(),**extra}).status_code == 422
    for extra in [{'customer_name':'  '},{'customer_phone':'abcdefghijk'}, {'subject':' '}, {'initial_message':'x'*4001}]:
        assert client.post(URL,json={**payload(),**extra}).status_code == 422

def test_messages_idempotency_conflict_close_and_reopen(client, signup):
    identity = register(client, signup)
    conv = create(client, assigned_user_id=identity['user']['id'])
    url = f"{URL}/{conv['id']}"
    message = {'request_id':str(uuid4()),'version':conv['version'],'kind':'manual_outbound','body':'Vou verificar seu pedido.'}
    result = client.post(url+'/messages',json=message)
    assert result.status_code == 201, result.text
    saved = result.json()
    assert saved['message']['kind'] == 'manual_outbound' and saved['conversation']['version'] == 2
    assert client.post(url+'/messages',json=message).json()['message']['id'] == saved['message']['id']
    assert client.post(url+'/messages',json={**message,'body':'Outro texto'}).status_code == 409
    assert client.post(url+'/messages',json={**message,'request_id':str(uuid4())}).status_code == 409
    assert client.patch(url,json={'version':1,'status':'closed'}).status_code == 409
    closed = client.patch(url,json={'version':2,'status':'closed'}).json()
    assert closed['closed_at'] and closed['status'] == 'closed'
    assert client.post(url+'/messages',json={**message,'request_id':str(uuid4()),'version':closed['version']}).status_code == 409
    assert client.patch(url,json={'version':closed['version'],'status':'quoting'}).status_code == 409
    reopened = client.patch(url,json={'version':closed['version'],'status':'human'}).json()
    assert reopened['closed_at'] is None and reopened['version'] == 4
    assert client.patch(url,json={'version':4,'status':'ai'}).status_code == 409
    assert client.post(url+'/messages',json={**message,'request_id':str(uuid4()),'version':4,'kind':'internal_note'}).status_code == 201
    recent = client.get(url+'/messages',params={'limit':2}).json()
    assert len(recent['items']) == 2 and recent['next_before']
    older = client.get(url+'/messages',params={'before':recent['next_before'],'limit':100}).json()
    assert all(m['id'] < recent['next_before'] for m in older['items'])
    assert 'Atendimento reaberto.' in [m['body'] for m in recent['items'] + older['items']]

def test_tenant_and_assignment_permissions(client, signup):
    alfa = register(client, signup); alfa_token = client.cookies.get(COOKIE_NAME)
    first = create(client)
    seller_input={'name':'Vendedor','email':'seller@example.com','password':'Senha-teste-123','role':'seller'}
    seller=client.post('/api/v1/users',json=seller_input).json()
    owned = create(client, assigned_user_id=alfa['user']['id'])
    beta = register(client, {**signup,'company':'Beta','email':'beta@example.com'})
    for suffix in ['', '/messages']:
        assert client.get(f"{URL}/{first['id']}"+suffix).status_code == 404
    assert client.patch(f"{URL}/{first['id']}",json={'version':1,'status':'closed'}).status_code == 404
    assert client.get(URL).json()['total'] == 0
    assert client.post(URL,json=payload(assigned_user_id=alfa['user']['id'])).status_code == 422
    client.cookies.clear();client.cookies.set(COOKIE_NAME,alfa_token)
    assert client.patch(f"{URL}/{first['id']}",json={'version':1,'assigned_user_id':beta['user']['id']}).status_code == 422
    client.post('/api/v1/auth/login',json={'email':seller_input['email'],'password':seller_input['password']})
    assert client.get(f"{URL}/{owned['id']}").status_code == 404
    assert client.get(URL).json()['total'] == 1
    url=f"{URL}/{first['id']}"
    assert client.patch(url,json={'version':1,'status':'closed'}).status_code == 403
    assert client.post(url+'/messages',json={'request_id':str(uuid4()),'version':1,'body':'Olá'}).status_code == 403
    claimed = client.patch(url,json={'version':1,'assigned_user_id':seller['id'],'status':'human'})
    assert claimed.status_code == 200, claimed.text
    assert client.patch(url,json={'version':2,'assigned_user_id':alfa['user']['id']}).status_code == 403
    assert client.post(URL,json=payload(assigned_user_id=alfa['user']['id'])).status_code == 403
    own = create(client)
    assert own['assigned_user']['id'] == seller['id']
    roster=client.get(URL+'/assignees').json()
    assert all('email' not in user for user in roster)
    assert beta['user']['id'] not in [user['id'] for user in roster]

def test_inactive_owner_trial_csrf_and_unauthenticated(client, signup, database):
    identity=register(client,signup)
    conv=create(client)
    with database() as db:
        db.get(User,identity['user']['id']).active=False;db.commit()
    assert client.get(URL).status_code == 401
    with database() as db:
        db.get(User,identity['user']['id']).active=True
        db.get(Company,identity['company']['id']).trial_ends_at=now()-1;db.commit()
    assert client.get(URL).status_code == 403
    assert client.post(URL,json=payload()).status_code == 403
    assert client.post(URL,json=payload(),headers={'Origin':'https://evil.example'}).status_code == 403
    client.cookies.clear()
    assert client.get(f"{URL}/{conv['id']}/messages").status_code == 401

def test_database_rejects_cross_tenant_assignment(client, signup, database):
    from sqlalchemy import update
    from sqlalchemy.exc import IntegrityError
    register(client,signup)
    conv=create(client)
    beta=register(client,{**signup,'email':'beta@example.com','company':'Beta'})
    with database() as db:
        with pytest.raises(IntegrityError):
            db.execute(update(Conversation).where(Conversation.id == conv['id']).values(assigned_user_id=beta['user']['id']))
        db.rollback()
