"""Inbound only: no AI or outgoing transport is invoked here."""
import hashlib
import re
from uuid import uuid4
from sqlalchemy import select, update
from app.core.security import now
from app.models.auth import Company
from app.models.conversations import Customer, Conversation, ConversationMessage
from app.models.whatsapp import WhatsAppNumber, WhatsAppReceipt

def receive(db, payload):
    if payload.get('object') != 'whatsapp_business_account':
        return
    for entry in payload.get('entry', []):
        for change in entry.get('changes', []):
            if change.get('field') != 'messages':
                continue
            value = change.get('value', {})
            phone_id = value.get('metadata', {}).get('phone_number_id')
            # A write lock serializes receipts/customer creation on SQLite and PostgreSQL.
            locked = db.execute(update(WhatsAppNumber).where(
                WhatsAppNumber.phone_number_id == phone_id,
                WhatsAppNumber.waba_id == entry.get('id'),
                WhatsAppNumber.active.is_(True)).values(revision=WhatsAppNumber.revision + 1))
            if not locked.rowcount:
                continue
            number = db.get(WhatsAppNumber, phone_id)
            company = db.get(Company, number.company_id)
            if not company or not company.active or (company.plan == 'trial' and company.trial_ends_at <= now()):
                continue
            for message in value.get('messages', []):
                if message.get('type') != 'text':
                    continue
                external = message.get('id', '')
                sender = message.get('from', '')
                body = message.get('text', {}).get('body', '')
                if not isinstance(external,str) or not 1 <= len(external) <= 200 or not isinstance(sender,str) or not re.fullmatch(r'\d{10,15}', sender) or not isinstance(body,str) or not 1 <= len(body) <= 4096:
                    continue
                if db.get(WhatsAppReceipt, (phone_id, external)):
                    continue
                customer = db.scalar(select(Customer).where(Customer.company_id == company.id, Customer.phone == sender))
                if not customer:
                    names = [c.get('profile',{}).get('name','') for c in value.get('contacts',[]) if c.get('wa_id') == sender]
                    name = names[0] if names and isinstance(names[0],str) and names[0].strip() else sender
                    customer = Customer(company_id=company.id, phone=sender, name=name[:120], business_name='', created_at=now())
                    db.add(customer)
                    db.flush()
                conv = db.scalar(select(Conversation).where(Conversation.company_id == company.id, Conversation.customer_id == customer.id, Conversation.channel == 'whatsapp', Conversation.status.not_in(['closed','converted'])).order_by(Conversation.created_at.desc()))
                if not conv:
                    conv = Conversation(company_id=company.id, customer_id=customer.id, subject='Conversa pelo WhatsApp', channel='whatsapp', status='new', request_id=str(uuid4()), request_hash=hashlib.sha256(external.encode()).hexdigest(), created_at=now(), updated_at=now(), version=1, opened_at=now(), handling_seconds=0)
                    db.add(conv)
                    db.flush()
                # Atomic increment preserves optimistic concurrency of human edits.
                db.execute(update(Conversation).where(Conversation.id == conv.id).values(version=Conversation.version + 1, updated_at=now()))
                try:
                    sent_at = min(int(message.get('timestamp',now())),now())
                    if sent_at < 0:
                        sent_at = now()
                except (ValueError,TypeError,OverflowError):
                    sent_at = now()
                stored = ConversationMessage(company_id=company.id, conversation_id=conv.id, kind='whatsapp_inbound', body=body, created_at=sent_at)
                db.add(stored)
                db.flush()
                db.add(WhatsAppReceipt(phone_number_id=phone_id, external_id=external, message_id=stored.id, received_at=now()))
                db.flush()
    db.commit()
