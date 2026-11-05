from fastapi import HTTPException
from sqlalchemy import select, func, or_, update, case
from sqlalchemy.exc import IntegrityError
from app.core.security import now
from app.models.conversations import Conversation, ConversationMessage as Message, ConversationRead as Read
from app.repositories.conversations import visible_query


def unread_query(context):
    return select(Message.conversation_id, func.count(Message.id).label('unread_count')).outerjoin(Read,
        (Read.company_id == Message.company_id) & (Read.conversation_id == Message.conversation_id) & (Read.user_id == context.user.id)
    ).where(Message.company_id == context.company.id, Message.kind != 'system', or_(Message.actor_id.is_(None), Message.actor_id != context.user.id), Message.id > func.coalesce(Read.last_message_id, 0), Message.conversation_id.in_(visible_query(context).with_only_columns(Conversation.id))).group_by(Message.conversation_id)


def unread_counts(db, context, ids=None):
    query = unread_query(context)
    if ids is not None:
        if not ids:
            return {}
        query = query.where(Message.conversation_id.in_(ids))
    return dict(db.execute(query).all())


def summary(db, context):
    visible = visible_query(context).subquery()
    counts = unread_counts(db, context)
    return {
        'company_id':context.company.id,
        'total': db.scalar(select(func.count()).select_from(visible)),
        'active': db.scalar(select(func.count()).select_from(visible).where(visible.c.status.not_in(['closed','converted']))),
        'unassigned': db.scalar(select(func.count()).select_from(visible).where(visible.c.assigned_user_id.is_(None), visible.c.status.not_in(['closed','converted']))),
        'unread_conversations':len(counts), 'unread_messages':sum(counts.values()),
    }


def mark_read(db, context, conv, last_message_id):
    seen = db.scalar(select(Message.id).where(Message.company_id == context.company.id, Message.conversation_id == conv.id, Message.id == last_message_id))
    if seen is None:
        raise HTTPException(422, 'O registro informado não pertence a este atendimento.')
    keys = dict(company_id=context.company.id, conversation_id=conv.id, user_id=context.user.id)
    predicate = (Read.company_id == context.company.id) & (Read.conversation_id == conv.id) & (Read.user_id == context.user.id)
    values = dict(last_message_id=case((Read.last_message_id < last_message_id,last_message_id),else_=Read.last_message_id),read_at=now())
    changed = db.execute(update(Read).where(predicate).values(**values))
    if not changed.rowcount:
        try:
            with db.begin_nested():
                db.add(Read(**keys,last_message_id=last_message_id,read_at=now()))
                db.flush()
        except IntegrityError:
            db.execute(update(Read).where(predicate).values(**values))
    db.commit()
    cursor = db.get(Read,(context.company.id,conv.id,context.user.id))
    db.refresh(cursor)
    return {'company_id':context.company.id,'conversation_id':conv.id,'last_message_id':cursor.last_message_id,'unread_count':unread_counts(db,context,[conv.id]).get(conv.id,0)}
