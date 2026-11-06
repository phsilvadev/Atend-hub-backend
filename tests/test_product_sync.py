import httpx
import pytest
from sqlalchemy import select, func
from app.api import products as api
from app.integrations import gestaoclick as adapter
from app.models.products import Product, ProductSync, ProductSyncItem
from app.models.gestaoclick import GestaoClickConnection
from app.models.auth import User
from test_gestaoclick import configure, ACCESS, SECRET

ORIGINAL_CLIENT = httpx.Client
PATH = '/api/v1/integrations/gestaoclick'

def prepare(client, database, signup, monkeypatch):
    configure(monkeypatch)
    identity = client.post('/api/v1/auth/register', json=signup).json()
    assert client.post(PATH, json={'version': 0, 'base_url': adapter.SERVER, 'access_token': ACCESS, 'secret_access_token': SECRET}).status_code == 200
    with database() as db:
        row = db.get(GestaoClickConnection, identity['company']['id'])
        row.selected_store_id = '2'; db.commit()
    return identity

def item(id='1', name='Metalon 30x30'):
    return {'id': id, 'nome': name, 'codigo_interno': 'M30', 'descricao': 'Descrição do ERP', 'nome_grupo': 'Metalon', 'ativo': '1', 'possui_variacao': '0', 'valor_venda': SECRET, 'estoque': 900}

def mock_pages(monkeypatch, pages, error_page=None):
    original = ORIGINAL_CLIENT
    calls = []
    def handler(request):
        calls.append(request)
        assert request.method == 'GET' and request.url.path == '/api/produtos'
        assert request.url.params['loja_id'] == '2' and request.url.params['limite'] == '100'
        assert request.headers['access-token'] == ACCESS and request.headers['secret-access-token'] == SECRET
        page = int(request.url.params['pagina'])
        if page == error_page:
            return httpx.Response(403, json={'message': SECRET})
        return httpx.Response(200, json={'code': 200, 'status': 'success', 'meta': {'pagina_atual': page, 'total_paginas': len(pages), 'total_registros': sum(map(len, pages))}, 'data': pages[page - 1]})
    monkeypatch.setattr(adapter.httpx, 'Client', lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    return calls

def begin(client):
    r = client.post(PATH + '/products-sync/start', json={'version': 1})
    assert r.status_code == 200, r.text
    return {'run_id': r.json()['run_id']}

def clock(monkeypatch):
    t = [api.now()]
    monkeypatch.setattr(api, 'now', lambda: t[0])
    return t

def test_atomic_paged_import_resumption_and_idempotent_update(client, database, signup, monkeypatch):
    identity = prepare(client, database, signup, monkeypatch)
    t = clock(monkeypatch)
    calls = mock_pages(monkeypatch, [[item()], [item('2', 'Chapa 3 mm')]])
    run = begin(client)
    assert client.post(PATH + '/products-sync/start', json={'version': 1}).status_code == 409
    first = client.post(PATH + '/products-sync/next', json=run)
    assert first.status_code == 200 and first.json()['processed'] == 1
    assert client.get('/api/v1/products').json()['total'] == 0  # Staged, not visible yet.
    assert client.post(PATH + '/products-sync/next', json=run).status_code == 429
    t[0] += 2
    second = client.post(PATH + '/products-sync/next', json=run)
    assert second.status_code == 200 and second.json()['status'] == 'completed'
    catalog = client.get('/api/v1/products').json()
    assert catalog['total'] == 2 and SECRET not in str(catalog)
    assert 'valor_venda' not in str(catalog) and 'estoque' not in str(catalog)
    assert client.get('/api/v1/products?q=Chapa').json()['total'] == 1
    assert client.get('/api/v1/products?q=%25').json()['total'] == 0
    assert client.post(PATH + '/products-sync/next', json=run).json()['status'] == 'completed'
    assert len(calls) == 2
    mock_pages(monkeypatch, [[item('1', 'Metalon atualizado')]])
    run = begin(client)
    assert client.post(PATH + '/products-sync/next', json=run).status_code == 200
    assert client.get('/api/v1/products').json()['total'] == 2  # Missing rows are not deleted.
    assert client.get('/api/v1/products?q=atualizado').json()['total'] == 1
    with database() as db:
        assert db.scalar(select(func.count()).select_from(ProductSyncItem)) == 0
        assert db.get(ProductSync, identity['company']['id']).last_success_at is not None


def test_failed_page_keeps_previous_catalog_and_purges_staging(client, database, signup, monkeypatch):
    prepare(client, database, signup, monkeypatch)
    t = clock(monkeypatch)
    mock_pages(monkeypatch, [[item()]])
    assert client.post(PATH + '/products-sync/next', json=begin(client)).status_code == 200
    mock_pages(monkeypatch, [[item('1', 'Alterado')], [item('2')]], error_page=2)
    run = begin(client)
    assert client.post(PATH + '/products-sync/next', json=run).status_code == 200
    t[0] += 2
    result = client.post(PATH + '/products-sync/next', json=run)
    assert result.status_code == 422 and SECRET not in result.text
    state = client.get(PATH + '/products-sync').json()
    assert state['status'] == 'failed' and state['error_code'] == 'permission_denied' and state['last_success_at']
    assert client.get('/api/v1/products').json()['items'][0]['name'] == 'Metalon 30x30'
    with database() as db:
        assert db.scalar(select(func.count()).select_from(ProductSyncItem)) == 0


def test_duplicates_abort_without_publication(client, database, signup, monkeypatch):
    prepare(client, database, signup, monkeypatch)
    mock_pages(monkeypatch, [[item(), item()]])
    assert client.post(PATH + '/products-sync/next', json=begin(client)).status_code == 409
    assert client.get('/api/v1/products').json()['total'] == 0


def test_configuration_change_during_io_is_discarded(client, database, signup, monkeypatch):
    identity = prepare(client, database, signup, monkeypatch)
    def changed(*args):
        with database() as db:
            row = db.get(GestaoClickConnection, identity['company']['id']); row.version += 1; db.commit()
        return [{'erp_id': '1', 'name': 'Old'}], 1, 1
    monkeypatch.setattr(api, 'product_page', changed)
    assert client.post(PATH + '/products-sync/next', json=begin(client)).status_code == 409
    assert client.get('/api/v1/products').json()['total'] == 0


def test_tenant_isolation_role_and_forged_company(client, database, signup, monkeypatch):
    identity = prepare(client, database, signup, monkeypatch)
    mock_pages(monkeypatch, [[item()]])
    run = begin(client)
    assert client.post(PATH + '/products-sync/next', json=run).status_code == 200
    with database() as db:
        db.get(User, identity['user']['id']).role = 'seller'; db.commit()
    assert client.get('/api/v1/products').json()['total'] == 1
    assert client.get(PATH + '/products-sync').status_code == 403
    assert client.post(PATH + '/products-sync/start', json={'version': 1}).status_code == 403
    client.post('/api/v1/auth/logout')
    other = client.post('/api/v1/auth/register', json={**signup, 'email': 'other@example.com', 'company': 'Outra empresa'})
    assert other.status_code == 201
    assert client.get('/api/v1/products').json()['total'] == 0
    assert client.post(PATH + '/products-sync/next', json=run).status_code == 404
    assert client.post(PATH + '/products-sync/start', json={'version': 1, 'company_id': identity['company']['id']}).status_code == 422


def test_live_empty_catalog_null_totals(monkeypatch):
    original = ORIGINAL_CLIENT
    def handler(request):
        return httpx.Response(200, json={'code': 200, 'status': 'success', 'meta': {'pagina_atual': 1, 'total_paginas': None, 'total_registros': None, 'proxima_pagina': None, 'proxima_url': None}, 'data': []})
    monkeypatch.setattr(adapter.httpx, 'Client', lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    assert adapter.product_page(adapter.SERVER, {'access_token': ACCESS, 'secret_access_token': SECRET}, '2', 1) == ([], 1, 0)

@pytest.mark.parametrize('payload', [
    {'code': 200, 'status': 'success', 'meta': {'pagina_atual': 1, 'total_paginas': 1001, 'total_registros': 100001}, 'data': []},
    {'code': 200, 'status': 'success', 'meta': {'pagina_atual': 2, 'total_paginas': 2, 'total_registros': 2}, 'data': [item()]},
    {'code': 200, 'status': 'success', 'meta': {'pagina_atual': 1, 'total_paginas': 1, 'total_registros': 1}, 'data': [{**item(), 'id': 'evil'}]},
])
def test_invalid_provider_contract_is_bounded(monkeypatch, payload):
    original = ORIGINAL_CLIENT
    monkeypatch.setattr(adapter.httpx, 'Client', lambda **kwargs: original(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)), **kwargs))
    with pytest.raises(adapter.ERPError): adapter.product_page(adapter.SERVER, {'access_token': ACCESS, 'secret_access_token': SECRET}, '2', 1)


def test_access_revoked_during_page_cannot_publish(client, database, signup, monkeypatch):
    identity = prepare(client, database, signup, monkeypatch)
    def revoked(*args):
        with database() as db:
            db.get(User, identity['user']['id']).active = False
            db.commit()
        return [{'erp_id': '1', 'name': 'Protected'}], 1, 1
    monkeypatch.setattr(api, 'product_page', revoked)
    result = client.post(PATH + '/products-sync/next', json=begin(client))
    assert result.status_code == 403
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Product)) == 0


def test_product_server_allowlist_precedes_http_client(monkeypatch):
    def forbidden(**kwargs): raise AssertionError('HTTP must not be attempted')
    monkeypatch.setattr(adapter.httpx, 'Client', forbidden)
    with pytest.raises(adapter.ERPError) as error:
        adapter.product_page('https://evil.example/api', {'access_token': ACCESS, 'secret_access_token': SECRET}, '2', 1)
    assert error.value.code == 'invalid_server'
