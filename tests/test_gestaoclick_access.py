import httpx
import pytest
from app.api import gestaoclick as api
from app.integrations import gestaoclick as adapter
from app.models.gestaoclick import GestaoClickConnection
from app.models.auth import User
from test_gestaoclick import configure,ACCESS,SECRET

PATH='/api/v1/integrations/gestaoclick'
DATA={'version':0,'base_url':adapter.SERVER,'access_token':ACCESS,'secret_access_token':SECRET}
STORES={'code':200,'status':'success','data':[{'id':'1','nome':'Matriz'},{'id':'2','nome':'Filial'}]}

def setup(client,signup,monkeypatch,response=STORES,status=200):
    configure(monkeypatch)
    identity=client.post('/api/v1/auth/register',json=signup).json()
    assert client.post(PATH,json=DATA).status_code==200
    original=httpx.Client
    calls=[]
    def handler(request):
        calls.append(request)
        assert str(request.url)==adapter.SERVER+'/lojas'
        assert request.method=='GET'
        assert request.headers['access-token']==ACCESS and request.headers['secret-access-token']==SECRET
        if response=='timeout':raise httpx.ReadTimeout(SECRET)
        return httpx.Response(status,json=response,headers={'Location':'https://attacker.example/api'})
    monkeypatch.setattr(adapter.httpx,'Client',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    return identity,calls


def test_access_and_store_selection_are_real_api_persistent_and_scoped(client,database,signup,monkeypatch):
    identity,calls=setup(client,signup,monkeypatch)
    response=client.post(PATH+'/test',json={'version':1})
    assert response.status_code==200
    result=response.json();assert result['status']=='access_validated' and result['stores']==[{'id':'1','name':'Matriz'},{'id':'2','name':'Filial'}]
    assert ACCESS not in response.text and SECRET not in response.text
    assert client.post(PATH+'/store',json={'version':2,'store_id':'99'}).status_code==422
    selected=client.post(PATH+'/store',json={'version':2,'store_id':'2'})
    assert selected.status_code==200 and selected.json()['selected_store_id']=='2'
    assert client.get(PATH).json()['selected_store_id']=='2'
    assert len(calls)==1  # Saving a store does not invoke another ERP endpoint.
    with database() as db:
        assert db.get(GestaoClickConnection,identity['company']['id']).selected_store_id=='2'
    assert client.post(PATH,json={**DATA,'version':3,'access_token':'replacement-only-test-access'}).status_code==200
    result=client.get(PATH).json();assert result['stores']==[] and result['selected_store_id'] is None and result['tested_at'] is None


@pytest.mark.parametrize('status,body,error_code,expected',[
    (401,{'code':401,'status':'error','data':{'mensagem':SECRET}},'credentials_rejected',422),
    (402,{'code':402,'status':'error'},'erp_plan_required',422),
    (403,{},'permission_denied',422),
    (429,{},'rate_limited',429),
    (500,{},'erp_unavailable',503),
    (302,{},'erp_unavailable',503),
    (200,{'code':401,'status':'error'},'credentials_rejected',422),
    (200,{'code':200,'status':'success','data':[{'id':'1','nome':None}]},'erp_unavailable',503),
    (200,'timeout','erp_unavailable',503),
])
def test_provider_errors_do_not_leak_tokens_or_log_out_user(client,signup,monkeypatch,status,body,error_code,expected):
    _,calls=setup(client,signup,monkeypatch,body,status)
    result=client.post(PATH+'/test',json={'version':1})
    assert result.status_code==expected
    assert ACCESS not in result.text and SECRET not in result.text
    saved=client.get(PATH).json();assert saved['test_error_code']==error_code and saved['status']=='test_failed' and saved['stores']==[]
    assert client.get('/api/v1/auth/me').status_code==200
    assert len(calls)==1


def test_untrusted_server_is_never_contacted(monkeypatch):
    def forbidden(**kwargs):raise AssertionError('Should not create an HTTP client')
    monkeypatch.setattr(adapter.httpx,'Client',forbidden)
    for url in ['http://api.gestaoclick.com/api','https://api.gestaoclick.com.attacker.example/api','https://127.0.0.1/api','https://api.gestaoclick.com/api?token=secret','https://custom.example.com/api']:
        with pytest.raises(adapter.ERPError) as error:adapter.list_stores(url,{'access_token':ACCESS,'secret_access_token':SECRET})
        assert error.value.code=='invalid_server'


def test_test_rate_limit_and_stale_store_selection(client,signup,monkeypatch):
    _,calls=setup(client,signup,monkeypatch)
    clock=[api.now()]
    monkeypatch.setattr(api,'now',lambda:clock[0])
    assert client.post(PATH+'/test',json={'version':1}).status_code==200
    assert client.post(PATH+'/test',json={'version':2}).status_code==429
    assert len(calls)==1
    clock[0]+=901
    assert client.post(PATH+'/store',json={'version':2,'store_id':'1'}).status_code==409


def test_permissions_and_cross_tenant_body_are_rejected(client,database,signup,monkeypatch):
    identity,calls=setup(client,signup,monkeypatch)
    assert client.post(PATH+'/test',json={'version':1,'company_id':'forged'}).status_code==422
    with database() as db:
        db.get(User,identity['user']['id']).role='seller';db.commit()
    assert client.post(PATH+'/test',json={'version':1}).status_code==403
    assert client.post(PATH+'/store',json={'version':1,'store_id':'1'}).status_code==403
    assert calls==[]


def test_changed_configuration_during_request_never_receives_old_result(client,database,signup,monkeypatch):
    identity,_=setup(client,signup,monkeypatch)
    def changed(*args):
        with database() as db:
            row=db.get(GestaoClickConnection,identity['company']['id']);row.version+=1;row.encrypted_credentials=None;db.commit()
        return [{'id':'1','name':'Old store'}]
    monkeypatch.setattr(api,'list_stores',changed)
    assert client.post(PATH+'/test',json={'version':1}).status_code==409
    result=client.get(PATH).json();assert result['stores']==[] and not result['has_credentials']
