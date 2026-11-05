import re
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import Field, EmailStr, TypeAdapter, field_validator, model_validator
from app.schemas.auth import StrictInput

DAYS = ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')

class DayHours(StrictInput):
    enabled: bool = False
    opens: str | None = None
    closes: str | None = None

    @model_validator(mode='after')
    def check_hours(self):
        if not self.enabled:
            self.opens = self.closes = None
            return self
        if not all(value and re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d', value) for value in (self.opens, self.closes)):
            raise ValueError('Informe horários válidos')
        if self.opens >= self.closes:
            raise ValueError('O encerramento deve ocorrer após a abertura no mesmo dia')
        return self

class CompanySettingsInput(StrictInput):
    name: str = Field(min_length=2, max_length=160)
    legal_name: str = Field(default='', max_length=160)
    tax_id: str = Field(default='', max_length=18)
    phone: str = Field(default='', max_length=24)
    email: str = Field(default='', max_length=254)
    postal_code: str = Field(default='', max_length=9)
    street: str = Field(default='', max_length=160)
    number: str = Field(default='', max_length=20)
    complement: str = Field(default='', max_length=100)
    district: str = Field(default='', max_length=100)
    city: str = Field(default='', max_length=100)
    state: str = Field(default='', max_length=2)
    timezone: str = Field(default='America/Sao_Paulo', max_length=64)
    business_hours: dict[Literal['mon','tue','wed','thu','fri','sat','sun'], DayHours] = Field(default_factory=lambda: {day: DayHours() for day in DAYS})

    @field_validator('*', mode='before')
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator('name')
    @classmethod
    def name_valid(cls, value):
        if len(value) < 2:
            raise ValueError('Nome inválido')
        return value

    @field_validator('tax_id')
    @classmethod
    def tax_valid(cls, value):
        value = re.sub(r'[./-]', '', value).upper()
        if not value:
            return value
        if not re.fullmatch(r'[A-Z0-9]{12}\d{2}', value) or len(set(value)) == 1:
            raise ValueError('CNPJ inválido')
        digits = [ord(c) - 48 for c in value]
        for size, weights in [(12, [5,4,3,2,9,8,7,6,5,4,3,2]), (13, [6,5,4,3,2,9,8,7,6,5,4,3,2])]:
            remainder = sum(d*w for d,w in zip(digits[:size], weights)) % 11
            if digits[size] != (0 if remainder < 2 else 11-remainder):
                raise ValueError('CNPJ inválido')
        return value

    @field_validator('email')
    @classmethod
    def email_valid(cls, value):
        return str(TypeAdapter(EmailStr).validate_python(value)).lower() if value else ''

    @field_validator('phone')
    @classmethod
    def phone_valid(cls, value):
        if value and (not re.fullmatch(r'\+?[\d ()-]+', value) or not 10 <= len(re.sub(r'\D', '', value)) <= 15):
            raise ValueError('Telefone inválido')
        return re.sub(r'[^\d+]', '', value)

    @field_validator('postal_code')
    @classmethod
    def postal_valid(cls, value):
        value = value.replace('-', '')
        if value and not re.fullmatch(r'\d{8}', value):
            raise ValueError('CEP inválido')
        return value

    @field_validator('state')
    @classmethod
    def state_valid(cls, value):
        value = value.upper()
        if value and value not in 'AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split():
            raise ValueError('UF inválida')
        return value

    @field_validator('timezone')
    @classmethod
    def timezone_valid(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError('Fuso horário inválido')
        return value

    @field_validator('business_hours')
    @classmethod
    def all_days(cls, value):
        if set(value) != set(DAYS):
            raise ValueError('Informe os sete dias da semana')
        return value

class CompanySettingsOutput(CompanySettingsInput):
    company_id: str
