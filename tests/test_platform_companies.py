from tests.test_auth import register
from tests.test_shared_knowledge import platform_login
from app.models.auth import Company, CompanyProfile
from app.core.security import now

URL='/api/v1/platform/companies'
def test_list_real_companies_filters_and_permissions(client,database,signup):
    alfa=register(client,signup)
    assert client.get(URL).status_code == 401
    beta=register(client,{**signup,'email':'beta@example.com','company':'Distribuidora Beta'})
    with database() as db:
        db.add(CompanyProfile(company_id=alfa['company']['id'],tax_id='11222333000181',email='contato@example.com'))
        db.get(Company,beta['company']['id']).trial_ends_at=now()-1
        db.commit()
    client.cookies.clear();platform_login(client,database)
    result=client.get(URL).json()
    assert result['total'] == 2 and result['summary']['trial'] == 1 and result['summary']['trial_expired'] == 1
    assert len(client.get(URL,params={'limit':1}).json()['items']) == 1
    assert client.get(URL,params={'status':'trial_expired'}).json()['items'][0]['id'] == beta['company']['id']
    assert client.get(URL,params={'q':'11.222.333/0001-81'}).json()['items'][0]['id'] == alfa['company']['id']
    assert client.get(URL,params={'q':'pedro@example.com'}).json()['total'] == 1
    assert client.get(URL,params={'q':'%'}).json()['total'] == 0
    assert 'password' not in str(result) and 'session' not in str(result)
    assert client.post(URL,json={}).status_code == 405
    assert client.patch(URL,json={}).status_code == 405
    assert client.get(URL,params={'limit':101}).status_code == 422
    assert client.get('/api/v1/users').status_code == 401
