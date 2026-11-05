import re
from sqlalchemy import select, or_, func
from app.models.conversations import Conversation, Customer


def visible_query(context):
    query = select(Conversation).where(Conversation.company_id == context.company.id)
    if context.user.role not in {'admin','supervisor'}:
        query = query.where(or_(Conversation.assigned_user_id == context.user.id, Conversation.assigned_user_id.is_(None)))
    return query


def find(db, context, conversation_id):
    return db.scalar(visible_query(context).where(Conversation.id == str(conversation_id)))


def listing(db, context, search, status, mine, offset, limit):
    query = visible_query(context).join(Customer, (Customer.id == Conversation.customer_id) & (Customer.company_id == Conversation.company_id))
    if search:
        search = search.strip()
        digits = re.sub(r'\D', '', search) if re.fullmatch(r'\+?[\d ()-]+', search) else ''
        phone_search = digits or search
        query = query.where(or_(Customer.name.icontains(search, autoescape=True), Customer.phone.contains(phone_search, autoescape=True), Customer.business_name.icontains(search, autoescape=True), Conversation.subject.icontains(search, autoescape=True)))
    if status:
        query = query.where(Conversation.status == status)
    if mine:
        query = query.where(Conversation.assigned_user_id == context.user.id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    return db.scalars(query.order_by(Conversation.updated_at.desc(), Conversation.id).offset(offset).limit(limit)).all(), total
