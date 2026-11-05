from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from tests.test_auth import register
from tests.test_conversations import create, URL
from app.core.config import COOKIE_NAME
from app.models.conversations import Conversation, ConversationRead, ConversationMessage
from sqlalchemy import select, func


def seller(client):
    data={'name':'Ana Souza','email':f'{uuid4()}@example.com','password':'Senha-teste-123','role':'seller'}
    result=client.post('/api/v1/users',json=data).json()
    client.cookies.clear()
    login=client.post('/api/v1/auth/login',json={key:data[key] for key in ('email','password')})
    assert login.status_code == 200
    return result,login.cookies.get(COOKIE_NAME)


def test_read_is_individual_monotonic_scoped_and_summary(client,signup):
    identity=register(client,signup);admin_token=client.cookies.get(COOKIE_NAME)
    user,token=seller(client)
    client.cookies.clear();client.cookies.set(COOKIE_NAME,admin_token)
    conv=create(client,assigned_user_id=user['id'])
    url=f"{URL}/{conv['id']}"
    first=client.post(url+'/messages',json={'request_id':str(uuid4()),'version':1,'kind':'internal_note','body':'Nota de Pedro'}).json()
    note_id=first['message']['id']
    client.cookies.clear();client.cookies.set(COOKIE_NAME,token)
    assert client.get(url).json()['unread_count'] == 2
    assert client.get(URL+'/summary').json()['unread_messages'] == 2
    assert client.get(URL,params={'unread_only':True}).json()['total'] == 1
    history=client.get(url+'/messages').json()['items']
    before_version=client.get(url).json()['version']
    assert client.post(url+'/read',json={'last_message_id':note_id}).json()['unread_count'] == 0
    stale=client.post(url+'/read',json={'last_message_id':history[0]['id']}).json()
    assert stale['last_message_id'] == note_id
    assert client.get(url).json()['version'] == before_version
    assert client.get(URL,params={'unread_only':True}).json()['total'] == 0
    assert client.post(url+'/read',json={'last_message_id':99999999}).status_code == 422
    client.post(url+'/messages',json={'request_id':str(uuid4()),'version':before_version,'body':'Resposta da Ana'})
    assert client.get(url).json()['unread_count'] == 0
    client.cookies.clear();client.cookies.set(COOKIE_NAME,admin_token)
    assert client.get(url).json()['unread_count'] == 1
    other=create(client,customer_phone='11999990123')
    foreign_message=client.get(f"{URL}/{other['id']}/messages").json()['items'][-1]['id']
    assert client.post(url+'/read',json={'last_message_id':foreign_message}).status_code == 422
    updates=client.get(url+'/updates',params={'after':note_id}).json()
    assert len(updates['messages']) == 1 and updates['conversation']['unread_count'] == 1
    register(client,{**signup,'email':'beta@example.com','company':'Beta'})
    assert client.get(url+'/updates').status_code == 404
    assert client.post(url+'/read',json={'last_message_id':note_id}).status_code == 404
    assert client.get(URL+'/summary').json()['unread_messages'] == 0


def test_times_exclude_closed_periods_and_note_is_not_response(client,signup,monkeypatch):
    from app.services import conversations as service
    register(client,signup)
    monkeypatch.setattr(service,'now',lambda:100)
    conv=create(client)
    url=f"{URL}/{conv['id']}"
    client.post(url+'/messages',json={'request_id':str(uuid4()),'version':1,'kind':'internal_note','body':'Nota não é resposta'})
    assert client.get(url).json()['first_response_at'] is None
    monkeypatch.setattr(service,'now',lambda:130)
    response=client.post(url+'/messages',json={'request_id':str(uuid4()),'version':2,'body':'Primeira resposta'}).json()
    assert response['conversation']['first_response_seconds'] == 30
    monkeypatch.setattr(service,'now',lambda:160)
    closed=client.patch(url,json={'version':3,'status':'closed'}).json()
    assert closed['handling_seconds'] == 60
    monkeypatch.setattr(service,'now',lambda:220)
    reopened=client.patch(url,json={'version':4,'status':'human'}).json()
    assert reopened['handling_seconds'] == 60
    monkeypatch.setattr(service,'now',lambda:250)
    closed_again=client.patch(url,json={'version':5,'status':'closed'}).json()
    assert closed_again['handling_seconds'] == 90
    assert closed_again['first_response_at'] == 130


def test_simultaneous_claim_has_single_winner(client,signup,database):
    identity=register(client,signup);admin_token=client.cookies.get(COOKIE_NAME)
    one,one_token=seller(client)
    client.cookies.clear();client.cookies.set(COOKIE_NAME,admin_token)
    two,two_token=seller(client)
    client.cookies.clear();client.cookies.set(COOKIE_NAME,admin_token)
    conv=create(client)
    def claim(person,token):
        return client.patch(f"{URL}/{conv['id']}",json={'version':1,'assigned_user_id':person['id'],'status':'human'},headers={'Cookie':f'{COOKIE_NAME}={token}'})
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(claim,one,one_token),pool.submit(claim,two,two_token)]
        codes=[future.result().status_code for future in futures]
    assert codes.count(200) == 1 and all(code in {200,404,409} for code in codes),codes
    with database() as db:
        assert db.get(Conversation,conv['id']).assigned_user_id in {one['id'],two['id']}
        assert db.get(Conversation,conv['id']).version == 2


def test_concurrent_duplicate_message_and_read_cursor(client,signup,database):
    identity=register(client,signup);token=client.cookies.get(COOKIE_NAME)
    conv=create(client)
    url=f"{URL}/{conv['id']}"
    data={'request_id':str(uuid4()),'version':1,'body':'Não duplicar registro'}
    def post():
        return client.post(url+'/messages',json=data,headers={'Cookie':f'{COOKIE_NAME}={token}'})
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(post),pool.submit(post)]
        results=[f.result() for f in futures]
    assert all(result.status_code == 201 for result in results),[r.text for r in results]
    assert results[0].json()['message']['id'] == results[1].json()['message']['id']
    ids=[row['id'] for row in client.get(url+'/messages').json()['items']]
    def read(message_id):
        return client.post(url+'/read',json={'last_message_id':message_id},headers={'Cookie':f'{COOKIE_NAME}={token}'})
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(read,ids[-1]),pool.submit(read,ids[0])]
        assert all(f.result().status_code == 200 for f in futures)
    with database() as db:
        cursor=db.get(ConversationRead,(identity['company']['id'],conv['id'],identity['user']['id']))
        assert cursor.last_message_id == ids[-1]
        assert db.scalar(select(func.count()).select_from(ConversationMessage).where(ConversationMessage.request_id == data['request_id'])) == 1


def test_read_migration_preserves_history_and_backfills_metrics(client,signup,database):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text
    register(client,signup)
    conv=create(client)
    client.post(f"{URL}/{conv['id']}/messages",json={'request_id':str(uuid4()),'version':1,'body':'Resposta antiga'})
    command.downgrade(Config('alembic.ini'),'20261105_manual_conversations')
    with database() as db:
        db.execute(text("UPDATE conversations SET created_at=100,updated_at=160,closed_at=160,status='closed' WHERE id=:id"),{'id':conv['id']})
        db.execute(text("UPDATE conversation_messages SET created_at=130 WHERE conversation_id=:id AND kind='manual_outbound'"),{'id':conv['id']})
        db.commit()
    command.upgrade(Config('alembic.ini'),'head')
    current=client.get(f"{URL}/{conv['id']}").json()
    assert current['first_response_seconds'] == 30 and current['handling_seconds'] == 60
    history=client.get(f"{URL}/{conv['id']}/messages").json()
    assert any(message['body'] == 'Resposta antiga' for message in history['items'])
