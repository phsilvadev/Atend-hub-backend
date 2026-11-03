# Atend-hub-backend

Backend do AtendeHub, plataforma de atendimento comercial para distribuidoras. Esta versão implementa apenas a autenticação multiempresa e o teste gratuito de 7 dias.

## Implementado

- Cadastro atômico de empresa, administrador e sessão.
- Trial de 7 dias calculado no servidor, com bloqueio após expiração.
- Login e logout reais, Argon2 e sessões revogáveis em cookie HttpOnly.
- Isolamento entre empresas, permissões por perfil e usuários do tenant.
- Proteção por origem em mutações, limite de tentativas e auditoria.
- Migrations Alembic e testes Pytest.

## Tecnologias

Python 3.12+, FastAPI, SQLAlchemy 2, Pydantic e Alembic. SQLite em desenvolvimento e testes. Sem Docker.

## Executar

Execute os comandos na raiz deste repositório:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

API: http://127.0.0.1:8000. OpenAPI: http://127.0.0.1:8000/docs. Liveness: `/health`.

O SQLite será criado em `data/atendehub.db`, ignorado pelo Git. Não há empresa ou usuário padrão. O cadastro cria a empresa e seu primeiro administrador.

## Configuração

- `DATABASE_URL`: conexão de desenvolvimento SQLite.
- `ALLOWED_ORIGINS`: lista JSON de origens do frontend, sem barra final. POST exige Origin ou Referer permitido, inclusive ao testar pela documentação interativa. Não amplie a lista para origens não confiáveis.
- `COOKIE_SECURE=false`: apenas em HTTP local. Produção exige true e HTTPS.
- `SESSION_HOURS=12`: validade da sessão normal.
- `REMEMBER_DAYS=7`: sessão persistente quando solicitado; não altera o trial.
- `APP_ENV=development`: produção recusa SQLite ou cookies/origens inseguros.

Credenciais e cookies não devem ser incluídos no Git ou nos logs. O `.env.example` contém apenas valores de desenvolvimento.

## Testar

```bash
pytest -q
alembic check
```

Os 20 testes utilizam bancos SQLite temporários e migrations; não apagam o banco de desenvolvimento. Cobrem cadastro, hashes, cookies, sessões, logout, permissões, isolamento, trial, CSRF, limites e upgrade/downgrade de migrations.

## Conexão com o frontend

Frontend separado: https://github.com/phsilvadev/AtendeHub.

O Next.js encaminha `/api/v1/*` à API pela variável privada `BACKEND_URL=http://127.0.0.1:8000`. No frontend, configure também `APP_ORIGIN` com sua origem pública. Cookies são mantidos no mesmo domínio do navegador. O backend deriva a empresa da sessão e não aceita company_id no cadastro de usuário.

## Limites e implantação

Este repositório publica o código; não provisiona hospedagem. Produção exige API Python com banco persistente, PostgreSQL validado, HTTPS, proxy confiável, monitoramento e backups. Não utilizar SQLite em produção. Configure limites adicionais na borda: atrás do proxy Next, a API observa o IP agregado do proxy, sem confiar automaticamente em X-Forwarded-For.

Recuperação por e-mail, WhatsApp, GestãoClick, OpenAI, cobrança e módulos comerciais permanecem pendentes. Não há superadmin público ou endpoint para alterar plano/renovar trial.

Consulte [API.md](API.md), [ARCHITECTURE.md](ARCHITECTURE.md) e [CHECKLIST.md](CHECKLIST.md).

Código inicial extraído de `backend/` do commit `c5c3276` do projeto AtendeHub, preservando o projeto original.
