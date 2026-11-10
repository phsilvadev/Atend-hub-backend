from datetime import datetime,timezone,date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
from sqlalchemy import select,delete
from app.models.ai_usage import AIUsage,AIPrice
from app.models.support import SupportTurn
from app.services import ai_accounting as accounting
from tests.test_shared_knowledge import platform_login,PASSWORD,ROOT
from tests.test_auth import register
from tests.test_support import ready,payload,answer
from app.services import support
URL=ROOT+'/ai-usage'


def price():return SimpleNamespace(input_usd=Decimal('0.4'),cached_usd=Decimal('0.1'),output_usd=Decimal('1.6'))

def test_decimal_math_cached_tokens_and_missing_usage():
    amount,status=accounting.calculate(1000000,250000,1000000,price())
    assert amount==Decimal('1.925') and status=='calculated'
    assert accounting.calculate(1,0,1,price())[0]==Decimal('0.000002')
    assert accounting.calculate(1000,None,100,price())==(Decimal('0.00056'),'estimated_cache')
    assert accounting.calculate(None,None,0,price())==(None,'unknown_usage')
    assert accounting.calculate(1,2,1,price())==(None,'unknown_usage')
    assert accounting.calculate(1,0,1,None)==(None,'unknown_price')


def add_usage(db,identity,**extra):
    fields=dict(id=str(uuid4()),company_id=identity['company']['id'],user_id=identity['user']['id'],feature='support',model='gpt-4.1-mini',status='complete',input_tokens=1000,output_tokens=100,cached_tokens=0,service_tier='default',created_at=int(datetime(2026,11,10,12,tzinfo=timezone.utc).timestamp()),finished_at=1,pricing_status='unknown_price')
    fields.update(extra);row=AIUsage(**fields);db.add(row);accounting.price_usage(db,row);db.commit();return row


def test_real_aggregation_filters_and_platform_only(client,database,signup):
    one=register(client,signup);two=register(client,{**signup,'company':'Beta','email':'beta-usage@example.com'})
    assert client.get(URL).status_code==401
    with database() as db:
        add_usage(db,one)
        add_usage(db,one,status='failed',input_tokens=None,output_tokens=None)
        add_usage(db,two,model='unknown-model')
    client.cookies.clear();platform_login(client,database)
    response=client.get(URL,params={'start':'2026-11-10','end':'2026-11-10','limit':1})
    assert response.status_code==200,response.text
    result=response.json();assert result['total']==3 and len(result['items'])==1
    assert result['summary']['input_tokens']==2000 and result['summary']['output_tokens']==200
    assert result['summary']['measured_requests']==2 and result['summary']['unmeasured_requests']==1
    assert result['summary']['unpriced_requests']==2 and Decimal(result['summary']['estimated_cost_usd'])==Decimal('0.00056')
    assert len(result['by_company'])==2 and result['currency']=='USD'
    assert client.get(URL,params={'start':'2026-11-10','end':'2026-11-10','company_id':one['company']['id']}).json()['total']==2
    assert client.get(URL,params={'start':'2026-11-10','end':'2026-11-10','status':'failed'}).json()['total']==1
    assert client.get(URL,params={'start':'2026-11-10','end':'2026-11-10','pricing':'unknown'}).json()['total']==2
    assert client.get(URL,params={'start':'2026-11-11','end':'2026-11-10'}).status_code==422
    assert client.get(URL,params={'start':'9999-12-31','end':'9999-12-31'}).status_code==422
    assert client.get(URL,params={'company_id':'not-a-uuid'}).status_code==422
    assert 'question' not in result['items'][0] and 'answer' not in result['items'][0]


def test_price_versions_explicit_apply_and_immutable_valued_history(client,database,signup):
    identity=register(client,signup)
    with database() as db:
        valued=add_usage(db,identity)
        unknown=add_usage(db,identity,model='custom-model')
        original_cost=valued.cost_usd
    client.cookies.clear();platform_login(client,database)
    data={'model':'custom-model','input_usd':'2','cached_usd':'0.5','output_usd':'8','effective_from':'2026-11-09','source_url':'https://developers.openai.com/api/docs/pricing','current_password':PASSWORD,'apply_to_unpriced':True}
    response=client.post(URL+'/prices',json=data)
    assert response.status_code==201,response.text
    assert response.json()['applied_records']==1 and response.json()['remaining_records']==0
    assert client.post(URL+'/prices',json=data).status_code==409
    assert client.post(URL+'/prices',json={**data,'model':'other','current_password':'wrong'}).status_code==403
    assert client.post(URL+'/prices',json={**data,'model':'other','source_url':'https://attacker.example'}).status_code==422
    assert client.post(URL+'/prices',json={**data,'model':'other','input_usd':'-1'}).status_code==422
    assert client.post(URL+'/prices',json={**data,'model':'other','input_usd':'0.1','cached_usd':'1'}).status_code==422
    assert client.post(URL+'/prices/'+response.json()['id']+'/apply',json={'current_password':PASSWORD}).json()['applied_records']==0
    with database() as db:
        assert db.get(AIUsage,valued.id).cost_usd==original_cost
        assert db.get(AIUsage,unknown.id).cost_usd==Decimal('0.0028')
    new=client.post(URL+'/prices',json={**data,'model':'gpt-4.1-mini','effective_from':'2026-11-10'})
    assert new.status_code==409  # seeded version cannot be overwritten
    with database() as db:assert db.get(AIUsage,valued.id).cost_usd==original_cost


def test_ledger_survives_chat_cleanup_and_replay(client,database,ready,monkeypatch):
    monkeypatch.setattr(support,'call_provider',answer)
    data=payload();turn=client.post('/api/v1/support/messages',json=data).json()
    assert client.post('/api/v1/support/messages',json=data).json()['id']==turn['id']
    with database() as db:
        usage=db.get(AIUsage,turn['id']);assert usage and usage.output_tokens==25
        assert len(list(db.scalars(select(AIUsage))))==1
        db.execute(delete(SupportTurn));db.commit();assert db.get(AIUsage,turn['id']) is not None


def test_provider_usage_survives_invalid_answer_and_non_standard_tier(client,database,ready,monkeypatch):
    def failed(*args):raise support.ProviderFailure(usage={'input_tokens':100,'output_tokens':20,'cached_tokens':0,'service_tier':'default'})
    monkeypatch.setattr(support,'call_provider',failed)
    turn=client.post('/api/v1/support/messages',json=payload()).json()
    with database() as db:
        usage=db.get(AIUsage,turn['id']);assert usage.status=='failed' and usage.cost_usd==Decimal('0.000072')
        usage.service_tier='priority';accounting.price_usage(db,usage);assert usage.cost_usd is None and usage.pricing_status=='unknown_tier'


def test_migration_backfills_without_prompts_or_fake_cache(client,database,ready,monkeypatch):
    from alembic import command
    from alembic.config import Config
    monkeypatch.setattr(support,'call_provider',answer)
    turn=client.post('/api/v1/support/messages',json=payload()).json()
    command.downgrade(Config('alembic.ini'),'20261110_support')
    command.upgrade(Config('alembic.ini'),'head')
    with database() as db:
        row=db.get(AIUsage,turn['id']);assert row is not None and row.cached_tokens is None
        assert row.pricing_status=='estimated_legacy' and row.cost_usd>0


def test_new_tariff_does_not_reprice_existing_calls(client,database,signup):
    identity=register(client,signup)
    with database() as db:old=add_usage(db,identity);old_id=old.id;old_cost=old.cost_usd
    client.cookies.clear();platform_login(client,database)
    response=client.post(URL+'/prices',json={'model':'gpt-4.1-mini','input_usd':'2','cached_usd':'0.5','output_usd':'8','effective_from':'2026-11-11','source_url':'https://developers.openai.com/api/docs/pricing','current_password':PASSWORD,'apply_to_unpriced':True})
    assert response.status_code==201,response.text
    with database() as db:
        later=add_usage(db,identity,created_at=int(datetime(2026,11,12,12,tzinfo=timezone.utc).timestamp()))
        assert later.cost_usd==Decimal('0.0028')
        assert db.get(AIUsage,old_id).cost_usd==old_cost


def test_usage_is_preserved_when_provider_response_cannot_be_rendered(client,database,ready):
    import httpx,json
    from unittest.mock import patch
    actual=httpx.Client
    body={'status':'completed','model':'gpt-4.1-mini-2025-04-14','service_tier':'default','output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':'not-json'}]}],'usage':{'input_tokens':1000,'output_tokens':100,'input_tokens_details':{'cached_tokens':250}}}
    with patch.object(support.httpx,'Client',side_effect=lambda **kw:actual(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=body)),trust_env=False,**kw)):
        result=client.post('/api/v1/support/messages',json=payload()).json()
    assert result['status']=='failed'
    with database() as db:
        row=db.get(AIUsage,result['id']);assert row.cached_tokens==250 and row.resolved_model=='gpt-4.1-mini-2025-04-14'
        assert row.cost_usd==Decimal('0.000485') and row.status=='failed'
