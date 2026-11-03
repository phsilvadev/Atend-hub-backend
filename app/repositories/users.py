from sqlalchemy import select
from app.models.auth import User

def by_email(db, email):
    return db.scalar(select(User).where(User.email == str(email).lower()))

def in_company(db, company_id, user_id=None):
    query = select(User).where(User.company_id == company_id)
    if user_id:
        return db.scalar(query.where(User.id == user_id))
    return db.scalars(query.order_by(User.name)).all()
