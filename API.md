# API — AtendeHub Auth, Fase 01

Base: `/api/v1`. Documentação OpenAPI da API local: `http://127.0.0.1:8000/docs`. Pelo frontend, use `/api/v1/...` na mesma origem. `/health` é exclusivo da API e retorna `{"status":"ok"}` (liveness, não readiness do banco).

## Autenticação e proteção

Sessão em cookie `atendehub_session`, HttpOnly/SameSite=Lax, Secure em produção. Nenhum token aparece em JSON. Login/cadastro criam a sessão. Logout revoga o token no banco. Envie cookies nas requisições seguintes.

POST exige `Origin` permitido ou `Referer` da origem permitida. Não use `company_id` ou papel no cadastro público: campos extras são rejeitados. A API obtém o tenant exclusivamente da sessão. Respostas auth não devem ser armazenadas em cache.

| Método | Caminho | Permissão | Resultado |
|---|---|---|---|
| POST | `/auth/register` | Público + origem válida | 201: empresa, admin, trial de 7 dias e cookie |
| POST | `/auth/login` | Público + origem válida | 200: identidade e novo cookie |
| GET | `/auth/me` | Sessão válida, empresa/usuário ativos | 200: identidade e estado do trial |
| POST | `/auth/logout` | Sessão válida + origem válida | 204: revogação e limpeza de cookie |
| GET | `/users` | Admin com trial vigente | 200: usuários da própria empresa |
| GET | `/users/{user_id}` | Admin com trial vigente | 200: usuário da própria empresa; 404 para outra empresa |
| POST | `/users` | Admin com trial vigente + origem válida | 201: usuário criado na empresa da sessão |

Os endpoints de usuários são a fundação de RBAC e isolamento. Não implementam edição, remoção, convites, troca de empresa ou administração da plataforma nesta fase.

## Cadastro

```http
POST /api/v1/auth/register
Origin: http://localhost:3000
Content-Type: application/json

{
  "name": "Ana Moreira",
  "company": "Minha Distribuidora",
  "email": "ana@example.com",
  "password": "uma-senha-forte-com-8-ou-mais-caracteres",
  "remember": false
}
```

`name`: 2–120 caracteres; `company`: 2–160; e-mail válido, normalizado em minúsculas e único globalmente; senha 8–128 caracteres (sem trim). Espaços externos dos nomes são removidos. `remember` é opcional, false por padrão. Company, admin e sessão são criados em uma única transação; falha reverte todos.

Estrutura da resposta (IDs/datas abaixo são apenas exemplos da documentação):

```json
{
  "user": {"id":"uuid-user","company_id":"uuid-company","name":"Ana Moreira","email":"ana@example.com","role":"admin","active":true},
  "company": {"id":"uuid-company","name":"Minha Distribuidora","plan":"trial","trial_started_at":1793664000,"trial_ends_at":1794268800},
  "trial_expired":false
}
```

Datas são segundos Unix UTC. `trial_ends_at - trial_started_at = 604800`. A expiração ocorre quando `agora >= trial_ends_at`. Não há renovação no login ou na criação de usuários.

## Login e logout

```json
{"email":"ana@example.com","password":"sua-senha","remember":true}
```

Login usa a mesma estrutura de resposta de cadastro/me. Cookie normal é de navegador, com validade de 12 horas no servidor por padrão. Com remember, cookie e sessão duram 7 dias. Trial e validade de sessão são independentes. Podem existir múltiplas sessões; logout revoga a sessão atual.

Logout: `POST /api/v1/auth/logout`, corpo `{}`. Trial vencido ainda permite me/logout, mas não operações de usuários. Sessão inválida/expirada recebe 401.

## Usuários da empresa

```json
{"name":"Vendedor","email":"vendedor@example.com","password":"uma-senha-forte","role":"seller"}
```

Perfis disponíveis: `admin`, `supervisor`, `seller`, `operator`. Somente `admin` pode listar/criar/consultar/editar usuários. `company_id`, `active` e outros campos extras não são aceitos. Senhas e hashes nunca são devolvidos. Não há perfil público `superadmin`.

## Erros

| HTTP | Significado |
|---|---|
| 401 | E-mail/senha inválidos, sessão inválida/expirada/revogada, empresa/usuário inativo |
| 403 | Origem inválida, papel sem permissão ou trial vencido |
| 404 | Usuário não pertence ao tenant ou não existe |
| 409 | E-mail indisponível, com rollback da transação |
| 422 | Validação de campos; entrada original e senhas não são ecoadas |
| 429 | Limite excedido; `Retry-After: 900` |
| 503 | Proxy Next não consegue acessar API; nenhum acesso é liberado |

Erro comum: `{"detail":"E-mail ou senha inválidos."}`. Trial: `{"detail":{"code":"trial_expired","message":"Seu período de teste terminou."}}`.

Limites persistidos em banco por janela de 15 minutos: login 10/e-mail e 50/IP; cadastro 5/e-mail e 25/IP, contando tentativas. O proxy deve aplicar limites adicionais em produção. Não há confiança automática em X-Forwarded-For; com proxy Next o limite de IP da API agrega requisições do proxy, enquanto o limite por e-mail continua específico. Validar política de proxy confiável antes de escalar.

## Exemplo curl local (dados da sua própria conta)

```bash
curl -i -c /tmp/atendehub-cookie.txt \
  -H 'Origin: http://localhost:3000' -H 'Content-Type: application/json' \
  --data '{"email":"ana@example.com","password":"sua-senha"}' \
  http://localhost:3000/api/v1/auth/login
curl -b /tmp/atendehub-cookie.txt http://localhost:3000/api/v1/auth/me
```

Proteja/remova o arquivo temporário de cookies após usar. Não compartilhe cookies ou registre credenciais em logs.

## Edição de usuário

`PATCH /api/v1/users/{user_id}` — sessão de administrador e trial válido. Corpo completo: `{"name":"Ana Souza","email":"ana@example.com","role":"seller","active":true}`. Retorna `UserOutput` (200), sem senha. Campos extras, inclusive `company_id` e `password`, são rejeitados (422).

O usuário é buscado exclusivamente na empresa da sessão: outro tenant ou ID inexistente retorna 404. E-mail já utilizado retorna 409 com rollback. Administradores não podem desativar ou rebaixar a própria conta (409). Alterações de e-mail, perfil ou ativação revogam as sessões do usuário; exige novo login. Operação registrada como `user.updated`, sem credenciais na auditoria. Origem da requisição validada contra CSRF.

## Configurações da empresa

`GET /api/v1/company/settings` — membros autenticados com empresa ativa e trial válido consultam exclusivamente a própria empresa. Retorna `company_id`, `name` (nome fantasia), `legal_name`, `tax_id` (CNPJ), `phone`, `email`, `postal_code`, `street`, `number`, `complement`, `district`, `city`, `state`, `timezone` e `business_hours`.

`PATCH /api/v1/company/settings` — somente administrador. Enviar os campos acima, exceto `company_id`. O corpo representa o formulário completo; `name` é obrigatório e os demais dados cadastrais podem permanecer vazios. IDs, plano, trial e credenciais não podem ser alterados por esse endpoint. Retorna os dados normalizados (200), ou 401/403/422. Origem validada contra CSRF. Alteração atômica do nome e perfil, auditada como `company.settings.updated` sem dados pessoais no evento.

```json
{
  "name": "Minha distribuidora",
  "timezone": "America/Sao_Paulo",
  "business_hours": {
    "mon": {"enabled": true, "opens": "08:00", "closes": "18:00"},
    "tue": {"enabled": false, "opens": null, "closes": null},
    "wed": {"enabled": false, "opens": null, "closes": null},
    "thu": {"enabled": false, "opens": null, "closes": null},
    "fri": {"enabled": false, "opens": null, "closes": null},
    "sat": {"enabled": false, "opens": null, "closes": null},
    "sun": {"enabled": false, "opens": null, "closes": null}
  }
}
```

CNPJ numérico ou alfanumérico validado pelos dígitos verificadores; CNPJ e CEP normalizados sem pontuação. Telefone de 10 a 15 dígitos, e-mail válido, UF brasileira e fuso IANA. Horários `HH:mm`, uma faixa por dia, com abertura anterior ao encerramento; dias inativos têm horários nulos. Não há suporte a virada de dia, intervalos de almoço ou feriados nesta etapa. Esses horários são configurações persistidas; não ativam automações de IA ou WhatsApp.

Empresas existentes mantêm o nome e seus registros. Sem perfil cadastrado, os campos adicionais são vazios e todos os dias ficam sem atendimento configurado. O GET não cria registros. Aplicar `alembic upgrade head` antes de iniciar a API atualizada.

## Planos e assinatura

`GET /api/v1/company/subscription` — sessão autenticada de qualquer perfil. A empresa é extraída da sessão, sem aceitar tenant por parâmetro. Retorna `company_id`, `plan_code`, `plan_name`, `current_plan`, `status` (`trial_active`, `trial_expired`, `active`), datas de trial em segundos Unix, `trial_days_remaining` arredondado para cima, contagem real de usuários totais/ativos, `billing_enabled:false` e `available_plans` do banco ordenados por posição/código.

Cada plano contém código, nome, descrição, `monthly_price_cents`, moeda BRL, `user_limit`, lista `features` e `is_demo`. O catálogo é global da plataforma; os dados de assinatura e usuários são isolados por empresa. Planos inativos não aparecem nas opções. Plano atual pode ser consultado mesmo após inativação do item de catálogo. Em produção, itens `is_demo` não são expostos como catálogo nem detalhes do plano atual. Sem itens no banco, a resposta contém catálogo vazio; o frontend não cria opções locais.

A consulta permanece acessível na API após expirar o trial, sem liberar módulos operacionais. O guard atual do workspace ainda bloqueia entrada após expiração; uma página de contratação fora do workspace segue pendente. Não há endpoint público para alterar plano, renovação, cobrança ou limites. Datas de cobrança não são fabricadas.

Seed demonstrativo explícito: `python -m app.seeds.plans`, somente em desenvolvimento/testes. Cria planos ausentes sem sobrescrever existentes. Valores fictícios: Essencial R$149/mês (3 usuários), Profissional R$349/mês (10), Empresarial R$799/mês (30). Recursos são propostas fictícias de catálogo, não habilitam módulos nem aplicam cotas reais. Não executar como carga comercial de produção.

## Central de atendimentos — etapa manual

Todas as rotas abaixo exigem sessão, empresa/usuário ativos e trial válido. `company_id`, canal, autor e horários são derivados no servidor. Administradores/supervisores veem e alteram todos os atendimentos de sua empresa; vendedores/operadores só veem os seus e os sem responsável. Recursos de outro tenant ou atribuídos a outro vendedor retornam 404.

| Método | Endpoint | Uso |
|---|---|---|
| GET | `/api/v1/conversations?q=&mine=false&offset=0&limit=50` | Busca por cliente, empresa do cliente, telefone ou assunto; filtros `status` e `mine`; `{items,total}`. Limite máximo 100. |
| GET | `/api/v1/conversations/assignees` | Pessoas ativas da empresa: somente id, nome e perfil, sem e-mail. |
| POST | `/api/v1/conversations` | Criação manual idempotente. |
| GET | `/api/v1/conversations/{id}` | Cliente, responsável, status, canal, datas e versão atual. |
| PATCH | `/api/v1/conversations/{id}` | Alterar status e/ou responsável com versão esperada. |
| GET | `/api/v1/conversations/{id}/messages?before=123&limit=100` | Últimas mensagens em ordem crescente; `next_before` permite carregar anteriores. Limite máximo 200. |
| POST | `/api/v1/conversations/{id}/messages` | Registrar mensagem manual ou nota interna, sem transporte externo. |

Criação:

```json
{
  "request_id": "22222222-2222-4222-8222-222222222222",
  "customer_name": "Carlos Mendes",
  "customer_phone": "(11) 99999-0101",
  "customer_business": "Construtora Vale",
  "subject": "Metalon 30x30 chapa 18",
  "assigned_user_id": null,
  "initial_message": "Solicitação registrada manualmente."
}
```

`request_id` deve ser um UUID novo por operação, reutilizado em tentativas da mesma operação. Mesma chave/corpo retorna o mesmo recurso; chave com conteúdo/ator diferente retorna 409. Clientes são reutilizados por telefone normalizado dentro da empresa. Formatos brasileiros de 10/11 dígitos sem `+` recebem prefixo 55; telefone internacional com `+` preserva o DDI. O cadastro existente não é sobrescrito por uma nova solicitação. Cliente mínimo não substitui o futuro módulo CRM.

Criar com responsável inicia `human`; sem responsável, `new`. Para vendedores/operadores, responsável é sempre o próprio usuário. Somente administradores/supervisores transferem para outras pessoas ou removem a atribuição; vendedores/operadores podem assumir um atendimento livre atribuindo-o a si mesmos. Responsável precisa estar ativo e pertencer à empresa.

PATCH: `{"version":1,"status":"quoting"}` ou `{"version":1,"assigned_user_id":"UUID"}`. Status manuais: `new`, `human`, `awaiting_customer`, `quoting`, `converted`, `closed`. `ai` está reservado e retorna 409 nesta etapa. Fechado deve ser reaberto como `human` antes de avançar; encerramento/reabertura e mudanças de responsável/status ficam no histórico. `converted` é uma marcação manual, sem confirmar venda no ERP nem emitir documento fiscal.

Registro de mensagem: `{"request_id":"UUID","version":2,"kind":"internal_note","body":"Confirmar disponibilidade."}`. Tipos aceitos: `manual_outbound` e `internal_note`. `customer_record` e `system` são criados apenas pelo servidor. Campo body: até 4.000 caracteres, sem branco vazio. Mensagens preservam ator e data. Não há envio WhatsApp, confirmação de entrega ou mensagem gerada pela IA.

Vendedores/operadores devem assumir o atendimento antes de alterar status ou registrar mensagens. Não é permitido registrar em status closed, converted ou ai: reabrir atendimento humano. Atualizações usam compare-and-swap por versão; mudanças concorrentes retornam 409. O frontend preserva o texto do usuário ao falhar e permite atualizar/revisar antes de tentar de novo. Criação e mensagens usam chaves únicas no banco; auditamos operações sem copiar corpo de mensagem para logs de auditoria.
