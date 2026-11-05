"""Provisionamento local explícito, sem cadastro público e sem senha na linha de comando."""
import argparse
from getpass import getpass
from app.core.database import SessionLocal
from app.services.platform_auth import bootstrap

def main():
    parser=argparse.ArgumentParser(description='Criar administrador da plataforma')
    parser.add_argument('--email',required=True)
    parser.add_argument('--name',required=True)
    args=parser.parse_args()
    password=getpass('Senha (mínimo 12 caracteres): ')
    if getpass('Confirme a senha: ') != password:
        raise SystemExit('As senhas não coincidem.')
    with SessionLocal() as db:
        try:
            bootstrap(db,args.name,args.email,password)
        except ValueError as error:
            raise SystemExit(str(error)) from None
    print('Administrador da plataforma criado. Nenhuma conta de empresa foi alterada.')

if __name__ == '__main__':
    main()
