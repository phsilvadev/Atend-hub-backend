"""Initialize an ignored local development encryption key, without printing it."""
import base64
import os
from pathlib import Path
from app.core.config import get_settings
from app.core.integration_secrets import key_bytes

def main():
    settings=get_settings()
    if settings.app_env!='development':
        raise SystemExit('Em produção, configure a chave no gerenciador de segredos da hospedagem.')
    if settings.whatsapp_credential_key.get_secret_value():
        key_bytes()
        print('Chave de criptografia já configurada; nenhum segredo foi alterado.')
        return
    key=base64.urlsafe_b64encode(os.urandom(32)).decode()
    path=Path('.env')
    if path.is_symlink():
        raise SystemExit('Configure a chave manualmente: .env é um link simbólico.')
    with open(path,'a',opener=lambda name,flags:os.open(name,flags|getattr(os,'O_NOFOLLOW',0),0o600)) as file:
        file.write(f'\nWHATSAPP_CREDENTIAL_KEY={key}\n')
    path.chmod(0o600)
    print('Chave local criada em .env ignorado pelo Git. Preserve-a e reinicie a API. O valor não foi exibido.')

if __name__=='__main__':
    main()
