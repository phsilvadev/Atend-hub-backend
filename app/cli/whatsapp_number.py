"""Bind an officially verified Meta number; never infer tenant from webhook input."""
import argparse
import re
from app.core.database import SessionLocal
from app.models.auth import Company
from app.models import conversations  # noqa: F401; register referenced message table
from app.models.whatsapp import WhatsAppNumber

def main():
    parser = argparse.ArgumentParser(description='Vincular número Meta já verificado à empresa. Não transfere números existentes.')
    parser.add_argument('--company-id',required=True)
    parser.add_argument('--phone-number-id',required=True)
    parser.add_argument('--waba-id',required=True)
    args = parser.parse_args()
    if not all(re.fullmatch(r'\d{1,40}',v) for v in [args.phone_number_id,args.waba_id]):
        parser.error('IDs Meta devem ser numéricos.')
    with SessionLocal() as db:
        if not db.get(Company,args.company_id):
            parser.error('Empresa não encontrada.')
        existing = db.get(WhatsAppNumber,args.phone_number_id)
        if existing:
            if existing.company_id != args.company_id or existing.waba_id != args.waba_id:
                parser.error('Número já vinculado; transferência automática proibida.')
        else:
            db.add(WhatsAppNumber(phone_number_id=args.phone_number_id,company_id=args.company_id,waba_id=args.waba_id))
            db.commit()
    print('Vínculo confirmado. Configure a assinatura messages no app Meta.')

if __name__ == '__main__':
    main()
