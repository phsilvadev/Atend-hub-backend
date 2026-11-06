"""Read-only adapter based on the customer's OpenAPI 3.1 document (GET /lojas)."""
import json
import re
import httpx

SERVER='https://api.gestaoclick.com/api'

class ERPError(Exception):
    def __init__(self,code,message,status=503):
        self.code=code
        self.message=message
        self.status=status
        super().__init__(code)  # No credentials or raw provider responses in exception text.

ERRORS={
    401:('credentials_rejected','O GestãoClick recusou as credenciais ou as regras de acesso do usuário. Confira tokens, validade, IP e horário.',422),
    402:('erp_plan_required','O plano do GestãoClick não permite usar a API. Libere esse recurso na conta do ERP.',422),
    403:('permission_denied','O usuário da chave não pode listar lojas. Verifique a permissão Lojas/index no GestãoClick.',422),
    429:('rate_limited','O limite de chamadas do GestãoClick foi atingido. Aguarde e tente novamente.',429),
}

def list_stores(base_url,credentials):
    if base_url!=SERVER:
        raise ERPError('invalid_server','Use o servidor confirmado no OpenAPI: https://api.gestaoclick.com/api.',422)
    try:
        with httpx.Client(timeout=8,follow_redirects=False) as client:
            with client.stream('GET',SERVER+'/lojas',headers={'access-token':credentials['access_token'],'secret-access-token':credentials['secret_access_token'],'Accept':'application/json'}) as response:
                raw=bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw)>1024*1024:
                        raise ERPError('invalid_response','O GestãoClick retornou uma resposta maior que o limite permitido.')
                try:
                    payload=json.loads(raw)
                except (ValueError,TypeError):
                    payload=None
                code=response.status_code
                if code==200 and isinstance(payload,dict) and type(payload.get('code')) is int:
                    code=payload['code']
                if code in ERRORS:
                    raise ERPError(*ERRORS[code])
                if code!=200:
                    raise ERPError('erp_unavailable','Não foi possível consultar o GestãoClick. Tente novamente mais tarde.')
                if not isinstance(payload,dict) or payload.get('status')!='success' or type(payload.get('code')) is not int or payload['code']!=200 or not isinstance(payload.get('data'),list) or len(payload['data'])>1000:
                    raise ERPError('invalid_response','O GestãoClick retornou dados diferentes do contrato documentado.')
                result=[]
                seen=set()
                for store in payload['data']:
                    if not isinstance(store,dict):
                        raise ValueError()
                    store_id=str(store.get('id',''))
                    name=store.get('nome')
                    if not re.fullmatch(r'[0-9]{1,40}',store_id) or store_id in seen or not isinstance(name,str) or not name.strip() or len(name)>160:
                        raise ValueError()
                    seen.add(store_id)
                    result.append({'id':store_id,'name':name})
                return result
    except ERPError:
        raise
    except (httpx.HTTPError,ValueError,TypeError,KeyError):
        raise ERPError('erp_unavailable','Não foi possível consultar o GestãoClick. Verifique a conexão e tente novamente.')


def product_page(base_url, credentials, store_id, page):
    """One bounded GET; provider-supplied pagination URLs are never followed."""
    if base_url != SERVER:
        raise ERPError('invalid_server', 'Use o servidor confirmado no OpenAPI.', 422)
    try:
        with httpx.Client(timeout=8, follow_redirects=False) as client:
            with client.stream('GET', SERVER + '/produtos', params={
                'loja_id': store_id, 'pagina': page, 'limite': 100,
            }, headers={'access-token': credentials['access_token'],
                        'secret-access-token': credentials['secret_access_token'],
                        'Accept': 'application/json'}) as response:
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 4 * 1024 * 1024:
                        raise ValueError()
                payload = json.loads(raw)
                code = response.status_code
                if code == 200 and isinstance(payload, dict) and type(payload.get('code')) is int:
                    code = payload['code']
                if code == 403:
                    raise ERPError('permission_denied', 'A chave não tem permissão Produtos/index no GestãoClick.', 422)
                if code in ERRORS:
                    raise ERPError(*ERRORS[code])
                if code != 200:
                    raise ERPError('erp_unavailable', 'Não foi possível consultar os produtos do GestãoClick.')
                if not isinstance(payload, dict) or payload.get('code') != 200 or payload.get('status') != 'success':
                    raise ValueError()
                rows, meta = payload.get('data'), payload.get('meta')
                if not isinstance(rows, list) or len(rows) > 100 or not isinstance(meta, dict):
                    raise ValueError()
                total_pages = meta.get('total_paginas')
                total = meta.get('total_registros')
                # The live ERP returns null totals for a successful empty first page.
                if not rows and page == 1 and total_pages is None and total is None and meta.get('proxima_pagina') is None and meta.get('proxima_url') is None:
                    total_pages, total = 0, 0
                if type(total_pages) is not int or not 0 <= total_pages <= 100 or type(total) is not int or not 0 <= total <= 10000 or meta.get('pagina_atual') != page or (total_pages == 0 and (total != 0 or rows)) or (total_pages > 0 and page > total_pages):
                    raise ValueError()
                products = []
                for row in rows:
                    if not isinstance(row, dict):
                        raise ValueError()
                    erp_id = str(row.get('id', ''))
                    if not re.fullmatch(r'[0-9]{1,40}', erp_id):
                        raise ValueError()
                    fields = {}
                    for source, target, limit in [('nome', 'name', 500), ('codigo_interno', 'code', 160), ('descricao', 'description', 10000), ('nome_grupo', 'category', 500)]:
                        value = row.get(source) or ''
                        if not isinstance(value, str) or len(value) > limit:
                            raise ValueError()
                        fields[target] = value
                    if not fields['name'].strip() or row.get('ativo') not in ('0', '1') or row.get('possui_variacao', '0') not in ('0', '1'):
                        raise ValueError()
                    products.append({'erp_id': erp_id, **fields, 'active': row['ativo'] == '1', 'has_variations': row.get('possui_variacao') == '1'})
                return products, max(1, total_pages), total
    except ERPError:
        raise
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        raise ERPError('invalid_response', 'Não foi possível ler o catálogo. Confira a conexão, os limites e o formato dos dados do ERP.')
