import hashlib
import json
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from app.core.security import now
from app.models.auth import User
from app.models.conversations import Customer, Conversation, ConversationMessage
from app.repositories import conversations as repository
from app.services.auth import audit

STATUS_NAMES = {'new':'Novo','human':'Em atendimento humano','awaiting_customer':'Aguardando cliente','quoting':'Em orçamento','converted':'Convertido em venda','closed':'Encerrado'}


def person(user):
    return {'id':user.id, 'name':user.name, 'role':user.role} if user else None


def output(db, conv):
    customer = db.scalar(select(Customer).where(Customer.id == conv.customer_id, Customer.company_id == conv.company_id))
    assignee = db.scalar(select(User).where(User.id == conv.assigned_user_id, User.company_id == conv.company_id)) if conv.assigned_user_id else None
    return {'id':conv.id, 'company_id':conv.company_id, 'customer':{'id':customer.id,'name':customer.name,'phone':customer.phone,'business_name':customer.business_name}, 'assigned_user':person(assignee), 'subject':conv.subject, 'status':conv.status,'channel':conv.channel,'created_at':conv.created_at,'updated_at':conv.updated_at,'closed_at':conv.closed_at,'version':conv.version}


def message_output(db, message):
    actor = db.scalar(select(User).where(User.id == message.actor_id, User.company_id == message.company_id)) if message.actor_id else None
    return {'id':message.id,'company_id':message.company_id,'conversation_id':message.conversation_id,'actor':person(actor),'kind':message.kind,'body':message.body,'created_at':message.created_at}


def get(db, context, conversation_id):
    conv = repository.find(db, context, conversation_id)
    if not conv:
        raise HTTPException(404, 'Atendimento não encontrado.')
    return conv


def assignee(db, context, user_id):
    if not user_id:
        return None
    user = db.scalar(select(User).where(User.id == str(user_id), User.company_id == context.company.id, User.active.is_(True)))
    if not user:
        raise HTTPException(422, 'Responsável indisponível nesta empresa.')
    return user.id


def system_message(db, context, conv, text):
    db.add(ConversationMessage(company_id=context.company.id, conversation_id=conv.id, actor_id=context.user.id, kind='system', body=text, created_at=now()))


def create(db, context, data):
    body_hash = hashlib.sha256(json.dumps({'actor':context.user.id, **data.model_dump(mode='json')}, sort_keys=True).encode()).hexdigest()
    existing = db.scalar(select(Conversation).where(Conversation.company_id == context.company.id, Conversation.request_id == str(data.request_id)))
    if existing:
        if existing.request_hash != body_hash:
            raise HTTPException(409, 'Esta solicitação já foi utilizada com outros dados.')
        return get(db, context, existing.id)
    owner = data.assigned_user_id
    if context.user.role not in {'admin','supervisor'}:
        if owner and str(owner) != context.user.id:
            raise HTTPException(403, 'Você só pode criar atendimentos sob sua responsabilidade.')
        owner = context.user.id
    owner = assignee(db, context, owner)
    customer = db.scalar(select(Customer).where(Customer.company_id == context.company.id, Customer.phone == data.customer_phone))
    if not customer:
        try:
            with db.begin_nested():
                customer = Customer(company_id=context.company.id, name=data.customer_name, phone=data.customer_phone, business_name=data.customer_business, created_at=now())
                db.add(customer)
                db.flush()
        except IntegrityError:
            customer = db.scalar(select(Customer).where(Customer.company_id == context.company.id, Customer.phone == data.customer_phone))
            if not customer:
                raise
    conv = Conversation(company_id=context.company.id, customer_id=customer.id, assigned_user_id=owner, subject=data.subject, status='human' if owner else 'new', channel='manual', request_id=str(data.request_id), request_hash=body_hash, created_at=now(), updated_at=now(), version=1)
    db.add(conv)
    try:
        db.flush()
        system_message(db, context, conv, f'Atendimento manual criado por {context.user.name}.')
        if data.initial_message:
            db.add(ConversationMessage(company_id=context.company.id, conversation_id=conv.id, actor_id=context.user.id, kind='customer_record', body=data.initial_message, created_at=now()))
        audit(db, context.user, 'conversation.created')
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Conversation).where(Conversation.company_id == context.company.id, Conversation.request_id == str(data.request_id)))
        if existing and existing.request_hash == body_hash:
            return get(db, context, existing.id)
        raise HTTPException(409, 'Não foi possível criar o atendimento. Atualize e tente novamente.')
    return conv


def change(db, context, conversation_id, data):
    conv = get(db, context, conversation_id)
    claiming = 'assigned_user_id' in data.model_fields_set and str(data.assigned_user_id) == context.user.id
    if context.user.role not in {'admin','supervisor'} and conv.assigned_user_id != context.user.id and not claiming:
        raise HTTPException(403, 'Assuma o atendimento antes de alterar seus dados.')
    if data.status == 'ai':
        raise HTTPException(409, 'Atendimento por IA ainda não está disponível.')
    values = {'updated_at':now(), 'version':Conversation.version + 1}
    events = []
    if 'assigned_user_id' in data.model_fields_set:
        owner = str(data.assigned_user_id) if data.assigned_user_id else None
        if context.user.role not in {'admin','supervisor'} and (owner != context.user.id or conv.assigned_user_id not in (None, context.user.id)):
            raise HTTPException(403, 'Somente administradores e supervisores podem transferir atendimentos.')
        owner = assignee(db, context, owner)
        values['assigned_user_id'] = owner
        if owner != conv.assigned_user_id:
            name = db.get(User, owner).name if owner else 'Sem responsável'
            events.append(f'Responsável alterado para {name}.')
    target_status = data.status or conv.status
    if conv.status == 'closed' and target_status not in {'closed','human'}:
        raise HTTPException(409, 'Reabra o atendimento em atendimento humano antes de alterar a etapa.')
    if data.status:
        values['status'] = data.status
        values['closed_at'] = (conv.closed_at or now()) if data.status == 'closed' else None
        if data.status != conv.status:
            events.append('Atendimento reaberto.' if conv.status == 'closed' else f'Status alterado para {STATUS_NAMES[data.status]}.')
    changed = db.execute(update(Conversation).where(Conversation.id == conv.id, Conversation.company_id == context.company.id, Conversation.version == data.version).values(**values))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, 'Este atendimento foi atualizado por outra pessoa. Atualize antes de salvar.')
    for event in events:
        system_message(db, context, conv, event)
    audit(db, context.user, 'conversation.updated')
    db.commit()
    db.refresh(conv)
    return conv


def add_message(db, context, conversation_id, data):
    conv = get(db, context, conversation_id)
    existing = db.scalar(select(ConversationMessage).where(ConversationMessage.company_id == context.company.id, ConversationMessage.conversation_id == conv.id, ConversationMessage.request_id == str(data.request_id)))
    if existing:
        if existing.body != data.body or existing.kind != data.kind or existing.actor_id != context.user.id:
            raise HTTPException(409, 'Esta solicitação de mensagem já foi usada com outro conteúdo.')
        return existing, conv
    if conv.status in {'closed','converted','ai'}:
        raise HTTPException(409, 'Reabra o atendimento humano antes de registrar novas mensagens.')
    if context.user.role not in {'admin','supervisor'} and conv.assigned_user_id != context.user.id:
        raise HTTPException(403, 'Assuma o atendimento antes de registrar mensagens.')
    changed = db.execute(update(Conversation).where(Conversation.id == conv.id, Conversation.company_id == context.company.id, Conversation.version == data.version).values(updated_at=now(), version=Conversation.version + 1))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, 'O atendimento mudou. Atualize o histórico antes de registrar a mensagem.')
    message = ConversationMessage(company_id=context.company.id, conversation_id=conv.id, actor_id=context.user.id, kind=data.kind, body=data.body, request_id=str(data.request_id), created_at=now())
    db.add(message)
    try:
        audit(db, context.user, 'conversation.message.recorded')
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(ConversationMessage).where(ConversationMessage.company_id == context.company.id, ConversationMessage.conversation_id == conv.id, ConversationMessage.request_id == str(data.request_id)))
        if not existing or existing.actor_id != context.user.id or existing.body != data.body or existing.kind != data.kind:
            raise HTTPException(409, 'Não foi possível registrar a mensagem. Atualize o atendimento.')
        message = existing
    db.refresh(conv)
    return message, conv
