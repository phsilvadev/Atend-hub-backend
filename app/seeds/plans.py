"""Explicit, idempotent demonstration seed. Never runs automatically in production."""
from app.core.config import get_settings
from app.models.auth import Plan

DEMO_PLANS = [
    dict(code='essential', name='Essencial', description='Para começar a organizar o atendimento da sua distribuidora.', monthly_price_cents=14900, user_limit=3, features=['Até 3 usuários', 'Central de atendimentos', 'Cadastro de clientes e produtos', 'Configurações da empresa']),
    dict(code='professional', name='Profissional', description='Para equipes comerciais que estão ampliando sua operação.', monthly_price_cents=34900, user_limit=10, features=['Até 10 usuários', 'Tudo do plano Essencial', 'Assistente de IA e base de conhecimento', 'Orçamentos e indicadores comerciais']),
    dict(code='enterprise', name='Empresarial', description='Para distribuidoras com uma operação comercial maior.', monthly_price_cents=79900, user_limit=30, features=['Até 30 usuários', 'Tudo do plano Profissional', 'Integração com ERP', 'Relatórios e acompanhamento da operação']),
]

def seed_plans(db, settings):
    if settings.app_env not in {'development', 'test'}:
        raise RuntimeError('Seed fictício permitido somente em desenvolvimento/testes.')
    added = 0
    for index, values in enumerate(DEMO_PLANS):
        if db.get(Plan, values['code']) is None:
            db.add(Plan(**values, currency='BRL', active=True, is_demo=True, sort_order=index))
            added += 1
    db.commit()
    return added

if __name__ == '__main__':
    from app.core.database import SessionLocal
    with SessionLocal() as db:
        print(f'{seed_plans(db, get_settings())} planos demonstrativos inseridos.')
