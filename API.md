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

### Leitura individual, contadores e sincronização da central

- `GET /api/v1/conversations/summary`: total visível, ativos (exceto closed/converted), ativos sem responsável, atendimentos com registros não lidos e quantidade de registros não lidos. O escopo é sempre o do usuário/empresa, independentemente dos filtros de busca da tela.
- `GET /api/v1/conversations?unread_only=true`: filtra atendimentos com registros não lidos para o usuário atual. Cada item/detalhe agora inclui `unread_count`, `first_response_at`, `first_response_seconds` e `handling_seconds`.
- `POST /api/v1/conversations/{id}/read` com `{"last_message_id":123}`: confirma leitura até o último registro mostrado. O ID precisa existir naquele atendimento/empresa. O cursor pertence exclusivamente ao usuário da sessão, avança de forma monotônica e não muda a versão, a ordenação ou o status do atendimento. Uma requisição atrasada nunca regride a leitura. Campos de empresa/usuário extras são rejeitados. Resposta: empresa, atendimento, cursor efetivo e contagem não lida restante.
- `GET /api/v1/conversations/{id}/updates?after=123`: retorna `conversation`, `messages` novos (até 200 em ordem crescente) e `has_more`. O próximo ciclo continua a partir do último ID efetivamente carregado. Todos os endpoints exigem sessão/trial/tenant ativos e a mesma autorização por responsável das demais rotas.

Não lidos: registros de cliente, mensagens manuais e notas de outras pessoas com ID posterior ao cursor. Eventos de sistema e registros escritos pelo próprio usuário não incrementam o contador. Uma leitura cobre o prefixo do histórico até o ID exibido (não um recibo de entrega do WhatsApp). Abrir a conversa e acompanhar o final do histórico confirma leitura; ao rolar para registros anteriores, novidades ficam pendentes até voltar ao final. A leitura de outra pessoa não afeta a sua.

Tempos: primeira resposta conta o primeiro `manual_outbound` após a criação, sem considerar notas internas/eventos de sistema. É tempo de registro manual, não de entrega externa. `handling_seconds` soma períodos abertos; closed/converted pausam a contagem e a reabertura inicia novo período, sem incluir o intervalo encerrado. Os cálculos são em segundos corridos, sem aplicar expediente/SLA comercial. A migration preenche métricas de registros existentes a partir dos horários salvos, sem gerar conteúdo fictício.

O frontend consulta novidades a cada 5 segundos enquanto visível, sem sobrepor ciclos. Retoma ao ganhar foco, preserva rascunho, histórico carregado e filtros/paginação. Falhas mostram estado de reconexão e tentam novamente; perda de sessão/expiração bloqueia a central e perda de atribuição limpa o histórico da tela. Isso é polling autenticado, não um canal público de eventos. IA/WhatsApp e seus recibos externos continuam nas fases próprias.

## Plataforma: acesso separado e conhecimento comum

Implementação e limites: [PLATFORM_KNOWLEDGE.md](docs/PLATFORM_KNOWLEDGE.md). As rotas de plataforma exigem cookie próprio e não aceitam sessão de empresa. Não existe cadastro público de superadmin. Provisionar com CLI; nenhum usuário/senha padrão.

| Método | Endpoint | Uso |
|---|---|---|
| POST | `/api/v1/platform/auth/login` | email/password; resposta id/nome/papel, cookie HttpOnly de 1h. |
| GET | `/api/v1/platform/auth/me` | Identidade de plataforma. |
| POST | `/api/v1/platform/auth/logout` | Revoga sessão e remove cookie. |
| POST | `/api/v1/platform/knowledge/imports` | Corpo JSON de arquivo autorizado; retorna somente conteúdo tratado e IDs dos rascunhos. |
| GET | `/api/v1/platform/knowledge/imports` | Importações tratadas, paginadas por offset/limit (máximo 50). |
| GET | `/api/v1/platform/knowledge/imports/{id}` | Detalhe tratado, restrito à plataforma. |
| GET/POST | `/api/v1/platform/knowledge` | Listar/criar rascunhos da biblioteca comum. |
| GET/PATCH | `/api/v1/platform/knowledge/{id}` | Consultar/editar revisão atual; PATCH exige versão. |
| GET | `/api/v1/platform/knowledge/{id}/revisions` | Revisões imutáveis do conteúdo. |
| POST | `/api/v1/platform/knowledge/{id}/publish` | Publicar após confirmação explícita da revisão. |
| POST | `/api/v1/platform/knowledge/{id}/deactivate` | Desativar com versão esperada. |
| GET | `/api/v1/knowledge?q=metalon&offset=0&limit=20` | Empresa autenticada com trial válido consulta somente biblioteca comum publicada/ativa. Busca textual, não semântica. |
| GET | `/api/v1/knowledge/{id}` | Apenas a revisão publicada; rascunhos/desativados retornam 404. |

Mutações exigem Origin/Referer configurado. Para uso direto local via curl, enviar `Origin: http://localhost:3000` (ou origem explicitamente configurada). Para usar Swagger diretamente na origem da API, configurar essa origem de desenvolvimento conscientemente em ALLOWED_ORIGINS; não há CORS aberto. O BFF do frontend atual não encaminha as novas rotas de plataforma.

Exemplo de corpo de arquivo JSON normalizado para importação:

```json
{
  "request_id":"22222222-2222-4222-8222-222222222222",
  "authorized":true,
  "authorization_reference":"Autorização de uso registrada pela administração da fonte.",
  "redaction_terms":["Nome do participante","Nome da empresa de origem"],
  "messages":[
    {"role":"customer","text":"O que é metalon?"},
    {"role":"agent","text":"É uma denominação comercial de tubos de aço de seção quadrada ou retangular. Verifique o catálogo técnico."}
  ]
}
```

Enviar com `--data-binary @arquivo.json`, Content-Type application/json e sessão de plataforma. Limites: 512 KiB de corpo real, 2–200 turnos, até 3.000 caracteres por turno. Papel customer/agent é explícito. `authorized` deve ser booleano true; referência e termos são entrada do operador. A verificação de autorização não é uma validação jurídica automática. IDs/hashes não substituem a revisão. Repetir request_id com mesmo corpo/operador retorna a mesma importação; corpo diferente retorna 409. Não publicar automaticamente os candidatos. O retorno contém `requires_manual_review:true`, método determinístico, contagem de redações e `truncated` nos turnos limitados após a redação.

Conteúdo manual: `{"title":"O que é metalon?","body":"Texto técnico revisado e baseado em fonte autorizada.","kind":"technical_document","category":"Tubos","source_reference":"Catálogo técnico autorizado"}`. Tipos: faq, technical_document, synonym, approved_answer. `commercial_policy`, company_id e outros campos extras são rejeitados. Preços/estoque oficiais permanecem no ERP da distribuidora; regras comerciais privadas não pertencem à biblioteca compartilhada.

PATCH acrescenta `version` do detalhe atual; cria nova revisão sem substituir a publicada anterior. Publicação: `{"version":1,"privacy_checked":true,"source_rights_confirmed":true,"commercial_isolation_checked":true,"review_note":"Conteúdo revisado, anonimizado, genérico e tecnicamente conferido."}`. As três confirmações booleanas são obrigatórias. Conflitos retornam 409; dados/contatos ou condições comerciais detectadas retornam 422. Desativação: `{"version":2}`. Cada ação avança a versão de controle, separada do número da revisão.

Clientes não recebem fontes importadas, textos brutos, dados do administrador ou revisão em rascunho; recebem título/corpo/categoria/fonte/revisão publicada com scope=platform. Não há envio WhatsApp, coleta automática de tenants, chamada OpenAI ou treinamento de modelo nestas APIs.

## Superadmin — listagem de empresas

`GET /api/v1/platform/companies?q=&status=all&offset=0&limit=20` — somente sessão de plataforma válida. Sessão de distribuidora não autoriza. Filtros status: all, active (ativa fora do trial), trial, trial_expired e inactive. Busca nome, razão social, CNPJ sem/ com pontuação, e-mail comercial e e-mail de administrador. Offset >= 0; limite 1–100.

Retorno `{items,total,summary}`: items contém id/nome/razão/CNPJ/e-mail comercial, primeiro administrador ativo em ordem alfabética, código/nome do plano, status, registered_at e trial_ends_at (nulo em plano fora do trial). registered_at utiliza o trial_started_at salvo no cadastro inicial, antes de existir renovação de trial. Summary traz total e contagens de cada status globais; total refere-se ao resultado filtrado. Não há preço ou informação financeira fabricada. Senhas/sessões nunca entram no retorno.

Operação auditada como platform.companies.list. Nenhum POST/PATCH para criação/edição foi disponibilizado. Frontend próprio em super-admin-atendehub, Next.js, com BFF restrito, middleware/proxy e proteção adicional no servidor. A origem local localhost:3001 precisa estar configurada explicitamente no backend.

## WhatsApp de entrada

- `GET /api/v1/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=...&hub.challenge=...`: retorna challenge em texto; 403 token inválido, 503 ausente.
- `POST /api/v1/webhooks/whatsapp`: JSON da Meta assinado por HMAC-SHA256 dos bytes originais em `X-Hub-Signature-256: sha256=...`. Limite real 1 MiB; 401 assinatura inválida, 400 estrutura inválida, 413 limite, 503 segredo ausente, 200 após commit ou evento não suportado. Única exceção POST à validação de Origin; demais endpoints preservam CSRF. Sem cookies de autenticação exigidos no webhook.
- Somente `object=whatsapp_business_account`, `changes[].field=messages`, tipo `text`, remetente numérico de 10–15 dígitos e body 1–4096 são importados. IDs externos até 200 caracteres; WABA/número devem ter vínculo cadastrado por CLI. Eventos sem vínculo, tipo não suportado e empresas bloqueadas são ignorados.
- `GET /api/v1/conversations` e histórico existentes incluem `channel=whatsapp` e `kind=whatsapp_inbound`; seguem permissões e isolamento já existentes. Não há resposta automática ou envio real. IDs externos permanecem no banco, associados ao ID da mensagem local.

## WhatsApp QR Code — painel do cliente

Exige cookie de sessão da empresa, usuário **admin**, empresa ativa e trial válido. POST também exige Origin permitido. O cliente nunca fornece company_id ou session_id; corpo é `{}`, campos extras são rejeitados.

- `GET /api/v1/integrations/whatsapp-qr`: `{company_id,enabled,status,qr_data_url,qr_expires_at,phone}`. `enabled` indica configuração do serviço, não conexão com celular. QR PNG é temporário e acessível somente ao admin.
- `POST /api/v1/integrations/whatsapp-qr/connect`: iniciar/reutilizar pareamento; 503 se gateway indisponível; nunca retorna token ou chaves de sessão.
- `POST /api/v1/integrations/whatsapp-qr/disconnect`: desativa vínculo antes de chamar logout; se gateway falhar retorna 503, mas callbacks já estão bloqueados. Pode repetir para concluir logout.
- `POST /api/v1/webhooks/whatsapp-qr`: exclusivo do gateway interno. Sem cookie/Origin, exige `x-bridge-timestamp` (epoch, tolerância 300s), `x-bridge-signature` HMAC-SHA256 hexadecimal de `timestamp + '.' + corpo original`, chave compartilhada. Corpo até 64KiB: `{session_id,external_id,sender,name,body,timestamp}`. Não aceita tenant arbitrário. Sessões antigas/inativas são ignoradas, replay de mensagem é deduplicado. 401 assinatura/timestamp inválido, 400 payload inválido, 503 desabilitado.

Estados do gateway: disconnected, connecting, qr, connected, error. Histórico da central inclui `channel=whatsapp_qr`, mensagens `kind=whatsapp_inbound`. Sem grupos/mídias/LID não resolvido, mensagens próprias ou importação histórica.

## Cadastro/ativação oficial com credencial protegida

Rotas exclusivas de admin da empresa autenticada, com CSRF/Origin em POST, active tenant e versionamento. Não aceitam company_id, host arbitrário ou App Secret no corpo. Rate limit de 10 tentativas por empresa/15 minutos para validação e ativação.

- `GET /api/v1/integrations/whatsapp-official`: metadados, IDs, `has_token`, `version`, `verified_at`, `diagnostics`, `webhook_url` público e flags da plataforma. Nunca retorna credenciais. Status disconnected/validated/receiving; receiving exige recebimento persistido posterior à validação atual.
- `POST /api/v1/integrations/whatsapp-official/connect`: `{phone_number_id,waba_id,version,access_token?}`. IDs numéricos, token 20–4096 ASCII sem whitespace/CRLF. Campo vazio deve ser omitido para reaproveitar token existente com mesmos IDs. Valida na Meta e salva cifrado; novo token obrigatório ao trocar IDs. Versão inicial 0. 422 dados/token inválidos, 409 versão/vínculo incompatível, 503 armazenamento seguro/Meta indisponível.
- `POST /api/v1/integrations/whatsapp-official/setup`: `{version,action:"subscribe"|"register",confirm:true,pin?}`. PIN obrigatório no register, exatamente seis dígitos, SecretStr e não persistido. Verifica aplicativo/permissões antes de chamar POST WABA/subscribed_apps ou Phone-ID/register. Só admite aplicativo da plataforma; sem App ID/Secret, operação bloqueada. Inscrição exige URL pública/verify token configurados. Não registra novamente número CONNECTED nem migra On-Premises. Reconsulta a Meta após sucesso e incrementa versão. Em timeout após alteração remota, revalide antes de repetir: não há garantia de rollback na Meta.
- `POST /api/v1/integrations/whatsapp-official/disconnect`: `{version}`. Apaga ciphertext, desativa roteamento local, preserva histórico. Não revoga token remoto nem desinscreve WABA compartilhada.

Campos de diagnóstico: aplicativo confirmado, permissões de gestão/messaging confirmadas, expiração, status do número, verificação de código, plataforma e aplicativo inscrito. Eles representam a última consulta, não monitoramento contínuo. GET não dispara consulta externa; Validar e salvar vazio revalida o token protegido. A chave de criptografia, App Secret, PIN e verify token não aparecem nas respostas.

## GestãoClick — configuração por empresa

Admin autenticado de tenant ativo/trial válido, Origin em POST e versionamento. Sem acesso externo ao ERP.
- `GET /api/v1/integrations/gestaoclick`: `{company_id,enabled,base_url,has_credentials,status,version,updated_at}`. Status not_configured/credentials_saved. Sem tokens/ciphertext.
- `POST /api/v1/integrations/gestaoclick`: `{version,base_url,access_token?,secret_access_token?}`. Versão inicial 0. HTTPS com host de domínio e caminho /api ou /v1, sem userinfo/query/fragment/porta não padrão/IP literal. Tokens ASCII visível até 4096 caracteres, opcionais somente para reutilizar valores com mesma URL. Nenhum company_id é aceito no corpo. 409 versão obsoleta, 422 dados ausentes/inválidos, 503 chave de criptografia indisponível.
- `POST /api/v1/integrations/gestaoclick/remove`: `{version}`. Apaga credenciais e URL locais e incrementa versão; preserva controle de concorrência. Não revoga credenciais no GestãoClick.

## GestãoClick — consulta de lojas autorizadas

Atualização do cadastro anterior (sem transporte): estas ações explícitas passam a consultar o ERP.

- `POST /api/v1/integrations/gestaoclick/test` — `{version}`. Apenas admin de tenant ativo; chave é lida/decifrada no backend. Faz um GET /lojas no servidor fixo confirmado no OpenAPI. Salva lojas/data/erro e incrementa versão. Erros ERP 401/402/403 viram 422 com mensagem segura; 429 preserva 429; timeout/servidor/contrato inválido viram 503. Servidor não autorizado retorna 422 antes de enviar as chaves. Falhas remotas persistem `test_error_code`, limpam lojas/seleção; consulte GET após erro para obter a versão atual. Tentativas locais bloqueadas antes da consulta não limpam diagnóstico anterior.
- `POST /api/v1/integrations/gestaoclick/store` — `{version,store_id}`. Escolhe somente ID da lista autorizada persistida no mesmo tenant; teste deve ter sido bem-sucedido há no máximo 900s. Não há outra chamada ERP nesta ação. 422 ID fora da lista, 409 versão/teste ausente ou vencido.
- `GET /api/v1/integrations/gestaoclick` — acrescenta stores (`[{id,name}]`), selected_store_id, tested_at e test_error_code. Status possíveis: not_configured, credentials_saved, access_validated, test_failed. Os estados são resultado da última consulta, não monitoração contínua nem comprovação de acesso ao catálogo.

Limites locais do teste: dez tentativas por 15min/tenant e intervalo mínimo de um segundo; 429 local pode conter Retry-After. Mudança/remoção de configuração durante a chamada descarta a resposta velha com 409. Seleção não muda o vínculo fixo de usuário/loja no GestãoClick.

### Catálogo GestãoClick — importação explícita
- `GET /api/v1/integrations/gestaoclick/products-sync`: administrador; diagnóstico da empresa da sessão.
- `POST /api/v1/integrations/gestaoclick/products-sync/start` com `{ "version": 3 }`: inicia uma execução e devolve `run_id`. Requer credenciais e loja salvas. Não faz HTTP ao ERP.
- `POST /api/v1/integrations/gestaoclick/products-sync/next` com `{ "run_id": "UUID" }`: consulta uma página de `GET /produtos?loja_id=...&pagina=...&limite=100`. Repita enquanto `status=running`, com intervalo mínimo de um segundo. A UI aguarda 1,1s. Recarregar/fechar pausa o processamento e permite retomada.
- Progresso: `company_id`, `run_id`, `status` (`idle/running/completed/failed`), `processed`, `pages_done`, `total_pages`, `started_at`, `completed_at`, `last_success_at`, `error_code`.
- `GET /api/v1/products?q=metalon&page=1`: usuários ativos da empresa; busca literal por nome/código, 20 itens/página. Resposta `{company_id,total,page,page_size,items}`. Itens: `id,erp_id,code,name,description,category,active,has_variations,synced_at`.
- Regras: 409 configuração/paginação alterada; 429 página em processamento ou intervalo; erros remotos sanitizados. IDs de empresa não são aceitos no corpo. Nenhum segredo aparece nas respostas.
- Importação em staging; publicação transacional apenas após validar todas as páginas e contagens. Chave única empresa + ID ERP. Repetir atualiza sem duplicar; produtos ausentes não são removidos. Sem chamadas de escrita no ERP.
- Até 100 páginas/10.000 produtos por execução e 4MiB/página. Limite excedido falha preservando catálogo anterior. Sem sincronização automática/worker nesta etapa.
- Não importa preços, custos, estoque, unidade comercial (ausente no contrato da listagem), composição ou variações individuais. `has_variations` somente sinaliza existência. Nenhum desses dados é inferido.

### Imagem privada do produto
- `POST /api/v1/products/{id}/image?version=0`: administrador da empresa, sessão válida e Origin permitido. Corpo binário (não multipart), Content-Type `image/jpeg`, `image/png` ou `image/webp`; máximo 5 MiB. A API decodifica e reencoda antes do armazenamento privado no Firebase. Resposta: `{company_id,product_id,has_image:true,image_version,image_updated_at}`. Não retorna caminho de objeto ou URL pública.
- `GET /api/v1/products/{id}/image`: usuários ativos da mesma empresa, WebP autenticado e sem cache. 404 para produto alheio/sem imagem; 401 sessão inválida; 503 falha de armazenamento.
- Upload: 409 versão alterada, 413 tamanho/arquivo vazio, 415 tipo não permitido, 422 imagem inválida, 429 limite de tentativas, 503 configuração/Storage indisponível. Falhas não atualizam a imagem anterior.
- `GET /api/v1/products` inclui `image_upload_enabled` no envelope e `has_image`, `image_version`, `image_updated_at` em cada item. Imagens locais são preservadas na sincronização ERP. Veja `docs/FIREBASE_STORAGE.md` para credenciais/IAM e regras privadas.
