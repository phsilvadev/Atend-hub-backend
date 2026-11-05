import re
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, model_validator
from app.schemas.auth import StrictInput

Status = Literal['new','ai','human','awaiting_customer','quoting','converted','closed']

class CreateConversation(StrictInput):
    request_id: UUID
    customer_name: str = Field(min_length=2, max_length=120)
    customer_phone: str = Field(min_length=10, max_length=24)
    customer_business: str = Field(default='', max_length=160)
    subject: str = Field(min_length=2, max_length=200)
    assigned_user_id: UUID | None = None
    initial_message: str = Field(default='', max_length=4000)

    @field_validator('customer_name','customer_business','subject','initial_message', mode='before')
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value,str) else value

    @field_validator('customer_phone')
    @classmethod
    def normalize_phone(cls, value):
        if not re.fullmatch(r'\+?[\d ()-]+', value):
            raise ValueError('Telefone inválido')
        digits = re.sub(r'\D','',value)
        if len(digits) in (10,11) and not value.startswith('+'):
            digits = '55' + digits
        if not 10 <= len(digits) <= 15:
            raise ValueError('Telefone inválido')
        return digits

class UpdateConversation(StrictInput):
    version: int = Field(ge=1)
    status: Status | None = None
    assigned_user_id: UUID | None = None

    @model_validator(mode='after')
    def has_changes(self):
        if not self.model_fields_set.intersection({'status','assigned_user_id'}):
            raise ValueError('Nenhuma alteração informada')
        if 'status' in self.model_fields_set and self.status is None:
            raise ValueError('Status inválido')
        return self

class CreateMessage(StrictInput):
    request_id: UUID
    version: int = Field(ge=1)
    kind: Literal['manual_outbound','internal_note'] = 'manual_outbound'
    body: str = Field(min_length=1, max_length=4000)

    @field_validator('body', mode='before')
    @classmethod
    def trim_body(cls, value):
        return value.strip() if isinstance(value,str) else value

class PersonOutput(BaseModel):
    id: str
    name: str
    role: str

class CustomerOutput(BaseModel):
    id: str
    name: str
    phone: str
    business_name: str

class ConversationOutput(BaseModel):
    id: str
    company_id: str
    customer: CustomerOutput
    assigned_user: PersonOutput | None
    subject: str
    status: Status
    channel: Literal['manual']
    created_at: int
    updated_at: int
    closed_at: int | None
    version: int
    unread_count: int
    first_response_at: int | None
    first_response_seconds: int | None
    handling_seconds: int

class ConversationList(BaseModel):
    items: list[ConversationOutput]
    total: int

class MessageOutput(BaseModel):
    id: int
    company_id: str
    conversation_id: str
    actor: PersonOutput | None
    kind: Literal['system','customer_record','manual_outbound','internal_note']
    body: str
    created_at: int

class MessagePage(BaseModel):
    items: list[MessageOutput]
    next_before: int | None

class MessageResult(BaseModel):
    message: MessageOutput
    conversation: ConversationOutput

class MarkRead(StrictInput):
    last_message_id: int = Field(ge=1)

class ReadOutput(BaseModel):
    company_id: str
    conversation_id: str
    last_message_id: int
    unread_count: int

class ConversationSummary(BaseModel):
    company_id: str
    total: int
    active: int
    unassigned: int
    unread_conversations: int
    unread_messages: int

class ConversationUpdates(BaseModel):
    conversation: ConversationOutput
    messages: list[MessageOutput]
    has_more: bool
