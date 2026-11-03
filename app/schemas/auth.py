from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

class StrictInput(BaseModel):
    model_config = ConfigDict(extra='forbid')

class LoginInput(StrictInput):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    remember: bool = False

    @field_validator('email', mode='before')
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

class RegisterInput(LoginInput):
    name: str = Field(min_length=2, max_length=120)
    company: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=8, max_length=128)

    @field_validator('name', 'company')
    @classmethod
    def clean_names(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError('Informe ao menos dois caracteres')
        return value

class UserInput(StrictInput):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Literal['admin', 'supervisor', 'seller', 'operator']

    @field_validator('email', mode='before')
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator('name')
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError('Nome inválido')
        return value

class UserOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    company_id: str
    name: str
    email: str
    role: str
    active: bool

class CompanyOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    plan: str
    trial_started_at: int
    trial_ends_at: int

class IdentityOutput(BaseModel):
    user: UserOutput
    company: CompanyOutput
    trial_expired: bool
