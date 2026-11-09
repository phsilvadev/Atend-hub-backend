import json
from uuid import uuid4
from sqlalchemy import select, func
from tests.test_auth import register
from app.core.config import COOKIE_NAME
from app.core.security import passwords, now
from app.models.knowledge import PlatformAdmin, PlatformSession, PlatformAudit, KnowledgeImport, KnowledgeEntry, KnowledgeApproval
from app.services.platform_auth import bootstrap, PLATFORM_COOKIE

ROOT='/api/v1/platform'
KB=ROOT+'/knowledge'
PASSWORD='Senha-plataforma-123!'

def platform_login(client,database):
    with database() as db:
        admin=bootstrap(db,'Gestor da plataforma','platform@example.com',PASSWORD)
        admin_id=admin.id
    response=client.post(ROOT+'/auth/login',json={'email':'platform@example.com','password':PASSWORD})
    assert response.status_code == 200,response.text
    return admin_id

def document(**changes):
    return {'title':'O que é metalon?', 'body':'Metalon é uma denominação comercial de tubos de aço de seção quadrada ou retangular. Confirme as especificações do catálogo do fabricante.', 'kind':'technical_document','category':'Tubos de aço','source_reference':'Catálogo técnico autorizado, revisão humana',**changes}

def approval(version):
    return {'version':version,'privacy_checked':True,'source_rights_confirmed':True,'commercial_isolation_checked':True,'review_note':'Texto revisado, sem dados privados, fonte autorizada e conteúdo técnico conferido.'}

def imported(**changes):
    return {'request_id':str(uuid4()),'authorized':True,'authorization_reference':'Autorização formal registrada para utilização didática do material.', 'redaction_terms':['João Silva','Construtora Particular'], 'messages':[
        {'role':'customer','text':'Sou João Silva da Construtora Particular, email joao@example.com e telefone (11) 99999-0101. O que é metalon?'},
        {'role':'agent','text':'Metalon é o nome comercial de tubos de aço de seção quadrada ou retangular.'},
        {'role':'customer','text':'Consegue desconto de 10% e frete grátis?'},
        {'role':'agent','text':'Preço negociado R$ 100,00 com pagamento em 30 dias.'},
    ],**changes}

def test_separate_platform_auth_no_public_elevation(client,database,signup):
    tenant=register(client,signup)
    assert client.get(KB).status_code == 401
    assert client.post(ROOT+'/auth/login',json={'email':signup['email'],'password':signup['password']}).status_code == 401
    assert client.post('/api/v1/users',json={'name':'Inválido','email':'x@example.com','password':'Senha-teste-123','role':'platform_admin'}).status_code == 422
    assert client.post(ROOT+'/auth/register',json={'email':'root@example.com'}).status_code == 404
    client.cookies.clear()
    admin_id=platform_login(client,database)
    assert client.get('/api/v1/users').status_code == 401
    assert client.get('/api/v1/auth/me').status_code == 401
    assert client.get(ROOT+'/auth/me').json()['role'] == 'platform_admin'
    assert 'password' not in client.get(ROOT+'/auth/me').text
    token=client.cookies.get(PLATFORM_COOKIE)
    response=client.post(ROOT+'/auth/logout')
    assert response.status_code == 204
    client.cookies.clear();client.cookies.set(PLATFORM_COOKIE,token)
    assert client.get(KB).status_code == 401
    with database() as db:
        assert passwords.verify(PASSWORD,db.get(PlatformAdmin,admin_id).password_hash)
    assert tenant['user']['role'] == 'admin'

def test_import_authorized_sanitized_no_auto_publish_and_idempotent(client,database):
    platform_login(client,database)
    payload=imported()
    result=client.post(KB+'/imports',json=payload)
    assert result.status_code == 201,result.text
    body=result.json()
    assert body['requires_manual_review'] and len(body['candidate_ids']) == 1
    assert body['authorization_reference'] == payload['authorization_reference']
    for private in ['João Silva','Construtora Particular','joao@example.com','99999-0101','R$ 100','10%']:
        assert private not in result.text
    again=client.post(KB+'/imports',json=payload).json()
    assert again['id'] == body['id'] and again['candidate_ids'] == body['candidate_ids']
    assert client.post(KB+'/imports',json={**payload,'messages':payload['messages'][:-1]}).status_code == 409
    assert client.post(KB+'/imports',json={**imported(),'authorized':False}).status_code == 422
    assert client.post(KB+'/imports',json={**imported(),'authorized':1}).status_code == 422
    candidate=client.get(KB+'/'+body['candidate_ids'][0]).json()
    assert not candidate['active'] and candidate['published_revision'] is None
    with database() as db:
        stored=json.dumps(db.get(KnowledgeImport,body['id']).sanitized_messages,ensure_ascii=False)
        assert 'João Silva' not in stored and 'joao@example.com' not in stored
        assert db.scalar(select(func.count()).select_from(KnowledgeImport)) == 1
        assert db.scalar(select(func.count()).select_from(KnowledgeEntry)) == 1
        assert db.scalar(select(func.count()).select_from(KnowledgeApproval)) == 0

def test_version_publication_privacy_and_tenant_read_only(client,database,signup):
    register(client,signup);tenant_token=client.cookies.get(COOKIE_NAME);client.cookies.clear()
    platform_login(client,database)
    entry=client.post(KB,json=document()).json();url=KB+'/'+entry['id']
    client.cookies.clear();client.cookies.set(COOKIE_NAME,tenant_token)
    assert client.get('/api/v1/knowledge').json()['total'] == 0
    assert client.get('/api/v1/knowledge/'+entry['id']).status_code == 404
    assert client.patch(url,json={**document(),'version':1}).status_code == 401
    client.cookies.clear()
    response=client.post(ROOT+'/auth/login',json={'email':'platform@example.com','password':PASSWORD})
    assert response.status_code == 200
    assert client.post(url+'/publish',json={'version':1}).status_code == 422
    assert client.post(url+'/publish',json={**approval(1),'privacy_checked':1}).status_code == 422
    published=client.post(url+'/publish',json=approval(1)).json()
    assert published['active'] and published['published_revision'] == 1
    revised=client.patch(url,json={**document(body='Conteúdo atualizado e pendente de revisão humana. Não está aprovado para consumo.'),'version':published['version']}).json()
    assert revised['current_revision'] == 2 and revised['published_revision'] == 1
    assert client.patch(url,json={**document(),'version':published['version']}).status_code == 409
    assert len(client.get(url+'/revisions').json()['items']) == 2
    client.cookies.clear();client.cookies.set(COOKIE_NAME,tenant_token)
    view=client.get('/api/v1/knowledge/'+entry['id']).json()
    assert view['revision'] == 1 and view['body'] == document()['body']
    assert 'import_id' not in view and 'admin_id' not in view and 'version' not in view
    assert client.get('/api/v1/knowledge',params={'q':'metalon'}).json()['total'] == 1
    assert client.get('/api/v1/knowledge',params={'q':'%'}).json()['total'] == 0
    register(client,{**signup,'email':'beta@example.com','company':'Beta'})
    assert client.get('/api/v1/knowledge/'+entry['id']).status_code == 200
    client.cookies.clear();client.post(ROOT+'/auth/login',json={'email':'platform@example.com','password':PASSWORD})
    deactivated=client.post(url+'/deactivate',json={'version':revised['version']})
    assert deactivated.status_code == 200
    client.cookies.clear();client.cookies.set(COOKIE_NAME,tenant_token)
    assert client.get('/api/v1/knowledge/'+entry['id']).status_code == 404

def test_shared_content_rejects_private_terms_and_import_size(client,database):
    platform_login(client,database)
    for body in ['Preço R$ 50,00 com desconto especial para a empresa.', 'Contato privado: cliente@example.com, confirmar disponibilidade.']:
        entry=client.post(KB,json=document(body=body)).json()
        assert client.post(KB+'/'+entry['id']+'/publish',json=approval(1)).status_code == 422
    assert client.post(KB,json={**document(),'kind':'commercial_policy'}).status_code == 422
    assert client.post(KB,json={**document(),'company_id':str(uuid4())}).status_code == 422
    assert client.post(KB+'/imports',content=b'x'*524289,headers={'Content-Type':'application/json'}).status_code == 413
    assert client.post(KB+'/imports',content=b'not-json',headers={'Content-Type':'application/json'}).status_code == 422
    assert client.post(KB,json=document(),headers={'Origin':'https://evil.example'}).status_code == 403

def test_session_expiration_and_disabled_platform_admin(client,database):
    admin_id=platform_login(client,database)
    with database() as db:
        db.scalar(select(PlatformSession)).expires_at=now()-1;db.commit()
    assert client.get(KB).status_code == 401
    client.cookies.clear();client.post(ROOT+'/auth/login',json={'email':'platform@example.com','password':PASSWORD})
    with database() as db:
        db.get(PlatformAdmin,admin_id).active=False;db.commit()
    assert client.get(KB).status_code == 401
    assert client.post(ROOT+'/auth/login',json={'email':'platform@example.com','password':PASSWORD}).status_code == 401

def test_no_automatic_collection_of_tenant_conversations(client,database,signup):
    from tests.test_conversations import create
    register(client,signup)
    create(client,initial_message='Conversa privada nunca deve alimentar automaticamente a base comum.')
    with database() as db:
        assert db.scalar(select(func.count()).select_from(KnowledgeImport)) == 0
        assert db.scalar(select(func.count()).select_from(KnowledgeEntry)) == 0

def test_bootstrap_does_not_overwrite_and_login_rate_limit(client,database):
    platform_login(client,database)
    with database() as db:
        import pytest
        with pytest.raises(ValueError): bootstrap(db,'Gestor','platform@example.com','Outra-senha-valida-123')
        with pytest.raises(ValueError): bootstrap(db,'X','bad@example.com','curta')
    for _ in range(9):
        assert client.post(ROOT+'/auth/login',json={'email':'platform@example.com','password':'errada'}).status_code == 401
    assert client.post(ROOT+'/auth/login',json={'email':'platform@example.com','password':'errada'}).status_code == 429

def test_review_required_normalized_fields_and_public_source_url(client,database):
    platform_login(client,database)
    item=client.post(KB,json=document(source_reference='https://fabricante.example/catalogo-tecnico')).json()
    assert client.post(KB+'/'+item['id']+'/publish',json={**approval(1),'review_note':' '*20}).status_code == 422
    assert client.post(KB+'/'+item['id']+'/publish',json=approval(1)).status_code == 200
    assert client.post(KB+'/imports',json=imported(authorization_reference=' '*20)).status_code == 422
    assert client.post(KB+'/imports',json=imported(messages=[{'role':'customer','text':' '},{'role':'agent','text':'Resposta'}])).status_code == 422


def test_knowledge_migration_does_not_modify_tenant_auth(client,database,signup):
    from alembic import command
    from alembic.config import Config
    identity=register(client,signup)
    command.downgrade(Config('alembic.ini'),'20261105_conversation_reads')
    command.upgrade(Config('alembic.ini'),'head')
    assert client.get('/api/v1/auth/me').json()['company']['id'] == identity['company']['id']
    assert client.get('/api/v1/knowledge').json()['total'] == 0

def test_shared_sales_language_without_private_commercial_rules(client,database):
    platform_login(client,database)
    entry=client.post(KB,json=document(title='Como responder a um pedido de desconto?',kind='approved_answer',category='Linguagem comercial',body='Acolha a solicitação e informe que as condições dependem de consulta e aprovação da distribuidora. Não prometa valores ou condições antes da confirmação.')).json()
    assert client.post(KB+'/'+entry['id']+'/publish',json=approval(1)).status_code == 200
    stock=client.post(KB,json=document(body='Temos 20 barras disponíveis em estoque para esta empresa.')).json()
    assert client.post(KB+'/'+stock['id']+'/publish',json=approval(1)).status_code == 422
    standard=client.post(KB,json=document(body='Identificadores como NBR 8800-2008 devem ser conferidos na fonte técnica original.')).json()
    assert client.post(KB+'/'+standard['id']+'/publish',json=approval(1)).status_code == 200


def test_platform_library_filters_counts_pagination_and_review_state(client,database):
    platform_login(client,database)
    draft=client.post(KB,json=document()).json()
    published=client.post(KB,json=document(title='Cantoneira de aço',category='Perfis',kind='faq')).json()
    published=client.post(f"{KB}/{published['id']}/publish",json=approval(1)).json()
    inactive=client.post(KB,json=document(title='Documento desativado')).json()
    inactive=client.post(f"{KB}/{inactive['id']}/publish",json=approval(1)).json()
    client.post(f"{KB}/{inactive['id']}/deactivate",json={'version':inactive['version']})
    result=client.get(KB,params={'limit':1}).json()
    assert len(result['items']) == 1 and result['total'] == 3
    assert result['summary'] == {'total':3,'review':1,'published':1,'inactive':1}
    assert result['categories'] == ['Perfis','Tubos de aço']
    assert client.get(KB,params={'offset':3}).json()['items'] == []
    assert client.get(KB,params={'q':'%'}).json()['total'] == 0
    assert client.get(KB,params={'q':'Cantoneira','kind':'faq','category':'Perfis','status':'published'}).json()['items'][0]['id'] == published['id']
    assert client.get(KB,params={'status':'review'}).json()['items'][0]['id'] == draft['id']
    updated=client.patch(f"{KB}/{published['id']}",json={**document(title='Cantoneira revisada'),'version':published['version']}).json()
    assert updated['published_revision'] == 1 and updated['current_revision'] == 2
    result=client.get(KB,params={'status':'review'}).json()
    assert result['total'] == 2 and result['summary']['published'] == 0
    assert client.get(KB,params={'status':'not_valid'}).status_code == 422
    client.cookies.clear()
    assert client.get(KB,params={'q':'Cantoneira'}).status_code == 401
