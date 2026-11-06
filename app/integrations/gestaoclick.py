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
