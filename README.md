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

### Edição de equipe
Administradores podem editar nome, e-mail, perfil e ativação de usuários da própria empresa via `PATCH /api/v1/users/{user_id}`. Mudanças de acesso revogam as sessões; não é permitido desativar ou rebaixar a própria conta. Consulte API.md.

### Configurações da empresa
Aplicar `.venv/bin/alembic upgrade head` antes de executar a API. A migration `20261105_company_profile` adiciona contato, endereço e horários sem modificar empresas existentes. Membros consultam o cadastro por `GET /api/v1/company/settings`; somente administradores alteram por `PATCH`, com auditoria e isolamento pelo tenant da sessão. Consulte API.md. Horários são apenas configuração nesta etapa; integrações continuam fora deste escopo.

### Planos — catálogo demonstrativo no banco

Aplicar migrations e, apenas no ambiente local de desenvolvimento, executar:

```bash
.venv/bin/alembic upgrade head
.venv/bin/python -m app.seeds.plans
```

O seed idempotente insere três planos fictícios sem sobrescrever os já cadastrados. Ele recusa produção. A migration cria somente estrutura; não insere preços. A API `GET /api/v1/company/subscription` entrega o catálogo do banco e a situação real da empresa autenticada. O frontend mostra preços/limites fictícios identificados, skeleton, estado vazio e confirmação informativa. Nenhuma contratação, pagamento ou aplicação de limites é executada nesta etapa. Planos demonstrativos são filtrados em produção.

### Planejamento completo
O [CHECKLIST.md](CHECKLIST.md) agora cobre os 14 módulos do [prompt mestre](docs/PROMPT_MESTRE.md), organizados nas 12 fases originais e na fase adicional de planos SaaS. O [histórico](docs/DEVELOPMENT_HISTORY.md) preserva as entregas anteriores. SQLite, ausência de Docker e recuperação de senha ao final refletem decisões posteriores do usuário. O roadmap completo não significa que todos os módulos estejam implementados.

### Central de atendimentos manual

Aplicar `.venv/bin/alembic upgrade head`. A migration `20261105_manual_conversations` adiciona clientes mínimos, conversas e histórico sem inserir exemplos. A central usa `/api/v1/conversations`: criar, listar/buscar, atribuir responsável, alterar status, encerrar/reabrir e registrar mensagens/notas. Admin e supervisor gerenciam a empresa; vendedor e operador operam os próprios atendimentos e podem assumir os livres. Foreign keys compostas, validação de tenant, versões e chaves de requisição protegem relações, conflitos e duplicações.

Canal exclusivamente manual nesta entrega. Registrar texto não envia WhatsApp, não ativa IA e não confirma venda no ERP. Clientes por telefone são apenas a base mínima para a central; o CRM completo continua pendente. API.md descreve contratos e permissões. Testes específicos: `tests/test_conversations.py`. Nenhuma conversa fictícia é criada em desenvolvimento ou produção pelo startup/migration.

### Central antes das integrações — leitura e atualização
A central possui contadores individuais, filtro Não lidos, confirmação de leitura, primeiro registro de resposta manual e tempo acumulado de atendimento (pausado ao encerrar/converter). Lista/histórico são atualizados a cada 5 segundos com aba visível, sem recarregar nem apagar rascunhos/histórico paginado. Alterações simultâneas mantêm a proteção por versão; leitura não interfere nessa versão. O painel remove registros cujo acesso é perdido por transferência.

Atualizar banco: `.venv/bin/alembic upgrade head`. A migration `20261105_conversation_reads` preserva conversas/mensagens e preenche as métricas históricas disponíveis. Testes: `tests/test_conversation_reads.py`. O núcleo da central está pronto para receber as integrações; criação por webhook, envio/recibos externos e execução/transferência automática de IA continuam dependentes das Fases 03/04. Nenhum Docker ou serviço externo foi executado nesta etapa.

### Base comum e superadministrador

A plataforma agora tem identidade/sessão próprias para gerir conhecimento comum de ferro e aço. O WhatsApp operacional permanece responsabilidade de cada cliente; na plataforma há apenas importação explícita de JSON autorizado, redação assistida, rascunhos, versões, revisão/publicação e desativação. As empresas consultam somente versões comuns publicadas. Conversas privadas nunca são coletadas automaticamente.

Executar `.venv/bin/alembic upgrade head` e provisionar a conta escolhida pelo operador com `.venv/bin/python -m app.cli.platform_admin --email seu-email@empresa.com.br --name "Seu nome"`; senha solicitada de forma interativa. Não existem credenciais padrão ou promoção pública. Consulte [PLATFORM_KNOWLEDGE.md](docs/PLATFORM_KNOWLEDGE.md) e API.md. Painel frontend de superadmin, parsers TXT/PDF, OpenAI e busca semântica continuam pendentes. Nenhuma conta real foi criada durante o desenvolvimento; testes usam somente dados fictícios temporários.
