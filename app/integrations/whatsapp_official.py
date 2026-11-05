"""Documented Meta Graph endpoints; fixed host, bounded time, sanitized errors."""
import hashlib
import hmac
import logging
import time
import httpx
from fastapi import HTTPException
from app.core.config import get_settings

# debug_token requires input_token in its query. Suppress third-party HTTP logs:
# the app records only generic operation/audit names, never URL/query/header/body.
logging.getLogger('httpx').disabled=True
logging.getLogger('httpcore').setLevel(logging.WARNING)

class Graph:
    def __init__(self,token):
        self.token=token
        self.settings=get_settings()
        self.deadline=time.monotonic()+11
        self.client=httpx.Client(follow_redirects=False)
    def close(self):
        self.client.close()
    def call(self,method,path,params=None,body=None,app_auth=False):
        remaining=self.deadline-time.monotonic()
        if remaining<=0:
            raise HTTPException(503,'A Meta demorou para responder. Tente novamente.')
        params=dict(params or {})
        secret=self.settings.whatsapp_app_secret.get_secret_value()
        token=f'{self.settings.whatsapp_app_id}|{secret}' if app_auth else self.token
        if secret and not app_auth:
            params['appsecret_proof']=hmac.new(secret.encode(),self.token.encode(),hashlib.sha256).hexdigest()
        try:
            response=self.client.request(method,f'https://graph.facebook.com/{self.settings.whatsapp_graph_version}/{path}',params=params,json=body,headers={'Authorization':'Bearer '+token},timeout=min(4,remaining))
            if response.status_code in {400,401,403}:
                raise HTTPException(422,'A Meta recusou a operação. Confira os identificadores, a validade do token e as permissões da conta.')
            if response.status_code!=200:
                raise HTTPException(503,'Não foi possível consultar a Meta. Tente novamente.')
            data=response.json()
            if not isinstance(data,dict):
                raise ValueError()
            return data
        except HTTPException:
            raise
        except (httpx.HTTPError,ValueError,TypeError):
            raise HTTPException(503,'Não foi possível consultar a Meta. Tente novamente.')

    def membership(self,phone_id,waba_id):
        params={'fields':'id,display_phone_number,verified_name','limit':'100'}
        verified=None
        for _ in range(10):
            data=self.call('GET',f'{waba_id}/phone_numbers',params=params)
            for phone in data.get('data',[]):
                if phone.get('id')==phone_id:
                    display=phone.get('display_phone_number','')
                    name=phone.get('verified_name','')
                    if not isinstance(display,str) or not display or len(display)>40 or not isinstance(name,str) or len(name)>160:
                        raise HTTPException(503,'A Meta retornou dados inesperados.')
                    verified={'display_phone_number':display,'verified_name':name}
                    break
            if verified:
                break
            paging=data.get('paging',{})
            cursor=paging.get('cursors',{}).get('after')
            if not paging.get('next') or not isinstance(cursor,str) or len(cursor)>2000:
                break
            params['after']=cursor
        if not verified:
            raise HTTPException(422,'O Phone Number ID não foi encontrado nesta conta WhatsApp Business. Confira os identificadores e as permissões do token.')
        return verified

    def diagnostics(self,phone_id,waba_id):
        settings=self.settings
        result={'app_confirmed':False,'scopes':[],'expires_at':None,'app_subscribed':None,'phone_status':None,'code_verification_status':None,'platform_type':None}
        if settings.whatsapp_app_id and settings.whatsapp_app_secret.get_secret_value():
            data=self.call('GET','debug_token',params={'input_token':self.token},app_auth=True).get('data',{})
            scopes=data.get('scopes',[])
            expiry=data.get('expires_at',0)
            data_expiry=data.get('data_access_expires_at',0)
            if not data.get('is_valid') or str(data.get('app_id'))!=settings.whatsapp_app_id or not isinstance(scopes,list) or 'whatsapp_business_management' not in scopes or any(isinstance(value,(int,float)) and value>0 and value<=time.time() for value in [expiry,data_expiry]):
                raise HTTPException(422,'O token está inválido, expirado, sem permissão de gestão ou pertence a outro aplicativo Meta. Use o aplicativo autorizado pela plataforma.')
            result.update(app_confirmed=True,scopes=[scope for scope in ['whatsapp_business_management','whatsapp_business_messaging'] if scope in scopes],expires_at=min([int(value) for value in [expiry,data_expiry] if isinstance(value,(int,float)) and value>0],default=None))
        phone=self.call('GET',phone_id,params={'fields':'id,status,code_verification_status,platform_type'})
        for field in ['status','code_verification_status','platform_type']:
            value=phone.get(field)
            if value is not None and (not isinstance(value,str) or len(value)>80):
                raise HTTPException(503,'A Meta retornou dados inesperados.')
            result['phone_status' if field=='status' else field]=value
        if result['app_confirmed']:
            apps=self.call('GET',f'{waba_id}/subscribed_apps').get('data',[])
            if not isinstance(apps,list):
                raise HTTPException(503,'A Meta retornou dados inesperados.')
            result['app_subscribed']=any(str(app.get('whatsapp_business_api_data',{}).get('id'))==settings.whatsapp_app_id for app in apps if isinstance(app,dict))
        return result

def validate_credentials(token,phone_id,waba_id):
    graph=Graph(token)
    try:
        verified=graph.membership(phone_id,waba_id)
        verified['diagnostics']=graph.diagnostics(phone_id,waba_id)
        return verified
    except (ValueError,TypeError,KeyError,AttributeError):
        raise HTTPException(503,'A Meta retornou dados inesperados.')
    finally:
        graph.close()

def setup_connection(token,phone_id,waba_id,action,pin=None):
    graph=Graph(token)
    try:
        graph.membership(phone_id,waba_id)
        state=graph.diagnostics(phone_id,waba_id)
        if not state['app_confirmed']:
            raise HTTPException(409,'A plataforma precisa configurar o aplicativo Meta antes desta operação.')
        if action=='register':
            if state['phone_status']=='CONNECTED':
                raise HTTPException(409,'O número já está registrado na Cloud API; não é necessário registrá-lo novamente.')
            if state['platform_type']=='ON_PREMISE':
                raise HTTPException(409,'A migração de um número On-Premises precisa de acompanhamento do suporte.')
            if 'whatsapp_business_messaging' not in state['scopes']:
                raise HTTPException(422,'O token precisa da permissão whatsapp_business_messaging para registrar o número.')
            response=graph.call('POST',f'{phone_id}/register',body={'messaging_product':'whatsapp','pin':pin})
        else:
            settings=get_settings()
            if not settings.whatsapp_verify_token.get_secret_value() or not settings.whatsapp_public_webhook_url:
                raise HTTPException(409,'O suporte precisa configurar a URL pública e a verificação do webhook da plataforma.')
            response=graph.call('POST',f'{waba_id}/subscribed_apps')
        if response.get('success') not in (True,'true'):
            raise HTTPException(503,'A Meta não confirmou a operação. Verifique a situação antes de repetir.')
        # Do not infer readiness from a successful POST: query the provider again.
        return graph.diagnostics(phone_id,waba_id)
    finally:
        graph.close()
