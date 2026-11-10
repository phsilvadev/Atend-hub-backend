from uuid import UUID
from pydantic import Field,field_validator
from app.schemas.auth import StrictInput
class SupportInput(StrictInput):
    request_id:UUID
    message:str=Field(min_length=1,max_length=1000)
    @field_validator('message',mode='before')
    @classmethod
    def trim(cls,value):return value.strip() if isinstance(value,str) else value

class SupportAnswer(StrictInput):
    answer:str=Field(min_length=1,max_length=4000)
    source_ids:list[str]=Field(max_length=8)
