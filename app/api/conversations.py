from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import active_tenant, Context
from app.core.database import get_db
from app.models.auth import User
from app.models.conversations import ConversationMessage
from app.schemas.conversations import CreateConversation, UpdateConversation, CreateMessage, ConversationOutput, ConversationList, MessagePage, MessageResult, PersonOutput, Status
from app.repositories import conversations as repository
from app.services import conversations as service

router = APIRouter(prefix='/api/v1/conversations', tags=['Atendimentos'])

@router.get('', response_model=ConversationList)
def list_conversations(q: str = Query(default='', max_length=100), status: Status | None = None, mine: bool = False, offset: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=100), context: Context = Depends(active_tenant), db: Session = Depends(get_db)):
    items, total = repository.listing(db, context, q, status, mine, offset, limit)
    return {'items':[service.output(db,item) for item in items], 'total':total}

@router.get('/assignees', response_model=list[PersonOutput])
def list_assignees(context: Context = Depends(active_tenant), db: Session = Depends(get_db)):
    users = db.scalars(select(User).where(User.company_id == context.company.id, User.active.is_(True)).order_by(User.name)).all()
    return [service.person(user) for user in users]

@router.post('', response_model=ConversationOutput, status_code=201)
def create_conversation(data: CreateConversation, context: Context = Depends(active_tenant), db: Session = Depends(get_db)):
    return service.output(db, service.create(db, context, data))

@router.get('/{conversation_id}', response_model=ConversationOutput)
def get_conversation(conversation_id: UUID, context: Context = Depends(active_tenant), db: Session = Depends(get_db)):
    return service.output(db, service.get(db, context, conversation_id))

@router.patch('/{conversation_id}', response_model=ConversationOutput)
def update_conversation(conversation_id: UUID, data: UpdateConversation, context: Context = Depends(active_tenant), db: Session = Depends(get_db)):
    return service.output(db, service.change(db, context, conversation_id, data))

@router.get('/{conversation_id}/messages', response_model=MessagePage)
def get_messages(conversation_id: UUID, before: int | None = Query(default=None, gt=0), limit: int = Query(default=100, ge=1, le=200), context: Context = Depends(active_tenant), db: Session = Depends(get_db)):
    conv = service.get(db, context, conversation_id)
    query = select(ConversationMessage).where(ConversationMessage.company_id == context.company.id, ConversationMessage.conversation_id == conv.id)
    if before is not None:
        query = query.where(ConversationMessage.id < before)
    rows = list(db.scalars(query.order_by(ConversationMessage.id.desc()).limit(limit + 1)).all())
    more = len(rows) > limit
    rows = list(reversed(rows[:limit]))
    return {'items':[service.message_output(db,item) for item in rows], 'next_before':rows[0].id if rows and more else None}

@router.post('/{conversation_id}/messages', response_model=MessageResult, status_code=201)
def post_message(conversation_id: UUID, data: CreateMessage, context: Context = Depends(active_tenant), db: Session = Depends(get_db)):
    message, conv = service.add_message(db, context, conversation_id, data)
    return {'message':service.message_output(db,message), 'conversation':service.output(db,conv)}
