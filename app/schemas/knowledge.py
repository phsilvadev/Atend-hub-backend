from typing import Literal
from uuid import UUID
from pydantic import Field, field_validator
from app.schemas.auth import StrictInput

class KnowledgeInput(StrictInput):
    title: str = Field(min_length=3,max_length=180)
    body: str = Field(min_length=10,max_length=30000)
    kind: Literal['faq','technical_document','synonym','approved_answer']
    category: str = Field(min_length=2,max_length=80)
    source_reference: str = Field(min_length=3,max_length=1000)

    @field_validator('*',mode='before')
    @classmethod
    def trim(cls,value):
        return value.strip() if isinstance(value,str) else value

class KnowledgeEdit(KnowledgeInput):
    version: int = Field(ge=1)

class VersionInput(StrictInput):
    version: int = Field(ge=1)

class PublishInput(VersionInput):
    privacy_checked: Literal[True]
    source_rights_confirmed: Literal[True]
    commercial_isolation_checked: Literal[True]
    review_note: str = Field(min_length=10,max_length=1000)

    @field_validator('review_note',mode='before')
    @classmethod
    def trim_review(cls,value):
        return value.strip() if isinstance(value,str) else value

    @field_validator('privacy_checked','source_rights_confirmed','commercial_isolation_checked',mode='before')
    @classmethod
    def explicit_confirmation(cls,value):
        if value is not True:
            raise ValueError('Confirmação explícita necessária')
        return value

class ImportTurn(StrictInput):
    role: Literal['customer','agent']
    text: str = Field(min_length=1,max_length=3000)

    @field_validator('text',mode='before')
    @classmethod
    def trim_text(cls,value):
        return value.strip() if isinstance(value,str) else value

class ImportInput(StrictInput):
    request_id: UUID
    authorized: Literal[True]
    authorization_reference: str = Field(min_length=10,max_length=500)
    redaction_terms: list[str] = Field(default_factory=list,max_length=100)
    messages: list[ImportTurn] = Field(min_length=2,max_length=200)

    @field_validator('authorization_reference',mode='before')
    @classmethod
    def trim_reference(cls,value):
        return value.strip() if isinstance(value,str) else value

    @field_validator('authorized',mode='before')
    @classmethod
    def explicit_authorization(cls,value):
        if value is not True:
            raise ValueError('Autorização explícita necessária')
        return value

    @field_validator('redaction_terms')
    @classmethod
    def valid_terms(cls,terms):
        cleaned=[term.strip() for term in terms]
        if any(not 2 <= len(term) <= 120 for term in cleaned):
            raise ValueError('Informe termos identificadores válidos')
        return cleaned
