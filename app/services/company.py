from app.models.auth import CompanyProfile
from app.schemas.company import CompanySettingsOutput
from app.services.auth import audit

def read_settings(db, company):
    profile = db.get(CompanyProfile, company.id)
    values = {column.name: getattr(profile, column.name) for column in CompanyProfile.__table__.columns} if profile else {}
    return CompanySettingsOutput(**{**values, 'company_id': company.id, 'name': company.name})

def save_settings(db, context, data):
    profile = db.get(CompanyProfile, context.company.id)
    if profile is None:
        profile = CompanyProfile(company_id=context.company.id)
        db.add(profile)
    context.company.name = data.name
    for key, value in data.model_dump(exclude={'name'}).items():
        setattr(profile, key, value)
    audit(db, context.user, 'company.settings.updated')
    db.commit()
    return read_settings(db, context.company)
