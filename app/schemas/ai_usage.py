from datetime import date
from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit
from pydantic import Field,SecretStr,field_validator
from app.schemas.auth import StrictInput
class PriceInput(StrictInput):
    model:str=Field(min_length=1,max_length=120,pattern=r'^[a-zA-Z0-9][a-zA-Z0-9._:-]*$')
    input_usd:Decimal=Field(ge=0,le=100000,max_digits=18,decimal_places=8)
    cached_usd:Decimal=Field(ge=0,le=100000,max_digits=18,decimal_places=8)
    output_usd:Decimal=Field(ge=0,le=100000,max_digits=18,decimal_places=8)
    effective_from:date
    source_url:str=Field(max_length=1000)
    apply_to_unpriced:bool=False
    current_password:SecretStr=Field(min_length=1,max_length=128)
    @field_validator('source_url')
    @classmethod
    def official_source(cls,value):
        url=urlsplit(value)
        if url.scheme!='https' or url.hostname not in ['developers.openai.com','openai.com','platform.openai.com'] or url.username or url.password or url.fragment or url.query:raise ValueError('Informe fonte oficial de preços OpenAI')
        return value

class ApplyPriceInput(StrictInput):
    current_password:SecretStr=Field(min_length=1,max_length=128)
