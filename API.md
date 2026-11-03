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

Perfis disponíveis: `admin`, `supervisor`, `seller`, `operator`. Somente `admin` pode listar/criar/consultar usuários. `company_id`, `active` e outros campos extras não são aceitos. Senhas e hashes nunca são devolvidos. Não há perfil público `superadmin`.

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
