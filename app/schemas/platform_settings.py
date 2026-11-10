from pydantic import EmailStr, Field, SecretStr, field_validator
from app.schemas.auth import StrictInput

class AdminCreate(StrictInput):
    name: str = Field(min_length=2,max_length=120)
    email: EmailStr
    password: SecretStr = Field(min_length=12,max_length=128)
    current_password: SecretStr = Field(min_length=1,max_length=128)
    @field_validator('name','email',mode='before')
    @classmethod
    def normalize(cls,value,info):
        return value.strip().lower() if info.field_name=='email' and isinstance(value,str) else value.strip() if isinstance(value,str) else value

class AdminEdit(StrictInput):
    version:int=Field(ge=1)
    name:str=Field(min_length=2,max_length=120)
    email:EmailStr
    active:bool
    password:SecretStr | None=Field(default=None,min_length=12,max_length=128)
    current_password:SecretStr=Field(min_length=1,max_length=128)
    @field_validator('name','email',mode='before')
    @classmethod
    def normalize(cls,value,info):
        return AdminCreate.normalize(value,info)

class OpenAIInput(StrictInput):
    version:int=Field(ge=1)
    model:str=Field(min_length=1,max_length=120,pattern=r'^[a-zA-Z0-9][a-zA-Z0-9._:-]*$')
    api_key:SecretStr | None=Field(default=None,min_length=20,max_length=512)
    current_password:SecretStr=Field(min_length=1,max_length=128)
    @field_validator('api_key')
    @classmethod
    def no_spaces(cls,value):
        if value is not None and (not value.get_secret_value().isascii() or any(c.isspace() for c in value.get_secret_value())):
            raise ValueError('Chave inválida')
        return value

class ConfigAction(StrictInput):
    version:int=Field(ge=1)
    current_password:SecretStr=Field(min_length=1,max_length=128)
