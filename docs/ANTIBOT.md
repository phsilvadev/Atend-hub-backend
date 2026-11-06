# Verificação antirrobô — Cloudflare Turnstile

## Cobertura
- Cliente: cadastro (`client_register`) e login (`client_login`).
- Superadmin: login (`platform_login`). Não existe cadastro público de superadministradores.
- A API verifica token antes de conferir senha ou criar empresa/sessão; preservar senha correta e políticas de autenticação é obrigatório. CSRF/Origin, cookies HttpOnly e rate limiting existentes foram mantidos. A verificação reduz automações; não substitui esses controles ou a proteção de tráfego da hospedagem.

`GET /api/v1/auth/challenge` e `GET /api/v1/platform/auth/challenge` devolvem apenas `{enabled,site_key,testing}`, sem cache. Os BFFs expõem somente esses recursos permitidos. O cliente recebe somente a chave pública e entrega `challenge_token` no POST; a chave secreta permanece no backend. Token é limitado a 2048 caracteres e protegido por SecretStr; nunca é devolvido nos erros, salvo em claro, colocado em URL ou registrado em logs.

Backend usa o endereço oficial fixo `https://challenges.cloudflare.com/turnstile/v0/siteverify`, TLS, timeout, sem redirects e resposta limitada a 64 KiB. Valida sucesso booleano, action esperado, hostname exato e timestamp (máximo 5 minutos; tolerância de relógio futuro de 60s). `challenge_uses` guarda apenas SHA-256 por até 6 minutos, com chave única para impedir reuso concorrente; tokens expirados são descartados em novas verificações. A validação consome o desafio inclusive se a senha estiver incorreta: o frontend renova o widget após cada tentativa. Falha/timeout do provedor, configuração ausente, expiração ou erro de script não liberam o formulário.

## Produção
Crie um widget em Cloudflare Dashboard → Turnstile, modo Managed, e registre os hostnames reais do cliente e superadmin. Um widget pode incluir ambos; os endpoints distinguem a finalidade pelo action. Não inclua protocolo/porta no hostname.

Somente no ambiente protegido do backend:
```dotenv
TURNSTILE_ENABLED=true
TURNSTILE_TESTING=false
TURNSTILE_SITE_KEY=<chave-publica-real>
TURNSTILE_SECRET_KEY=<chave-secreta-real>
TURNSTILE_ALLOWED_HOSTNAMES=["cliente.seudominio.com","admin.seudominio.com"]
```
Reinicie o backend após alterar as variáveis. Frontends consultam a configuração pública em runtime, sem necessidade de chave secreta ou `NEXT_PUBLIC_*`. As origens completas HTTPS também precisam constar em `ALLOWED_ORIGINS` e no `APP_ORIGIN` próprio de cada frontend. Se adicionar CSP, autorize os scripts/frames oficiais de challenges.cloudflare.com conforme a documentação Cloudflare.

`APP_ENV=production` recusa inicialização sem Turnstile ativado, com modo de teste ou com chaves públicas de teste. Também continua exigindo HTTPS/cookies seguros e PostgreSQL. Chaves reais/domínios e validação da infraestrutura de produção ainda são pré-requisitos à publicação no Railway; não publicar com chaves fictícias.

## Desenvolvimento e testes
O .env local foi configurado com o par público oficial de sucesso da Cloudflare e `TURNSTILE_TESTING=true`. O widget mostra explicitamente que está em modo de teste. Esse modo chama o Siteverify real, mas usa o contrato de teste: hostname `example.com`, sem action e token dummy constante; por isso a checagem de action/hostname e o consumo no banco são substituídos somente para esse par oficial, com flag explícita fora de produção. Isso NÃO comprova detecção real de bots. Os testes de segurança sem esse modo usam HTTP simulado para cobrir domínio, action, timestamp e replay.

Testes backend: `pytest tests/test_turnstile.py`. Os testes existentes isolam a flag local para não depender da configuração .env. E2E de cada frontend:
```bash
BACKEND_SOURCE_DIR=../Atend-hub-backend E2E_TURNSTILE_TEST=1 npm run test:e2e -- e2e/turnstile.spec.ts
```
Os runners usam SQLite temporário e pares oficiais de teste, sem inserir usuários de teste no banco de desenvolvimento. O navegador carrega o widget oficial e a API chama a Cloudflare; não há bypass de token no backend de produção. Prints desktop/mobile mostram o modo de teste.

Fontes consultadas em 06/nov/2026:
- https://developers.cloudflare.com/turnstile/get-started/server-side-validation/
- https://developers.cloudflare.com/turnstile/get-started/client-side-rendering/
- https://developers.cloudflare.com/turnstile/troubleshooting/testing/
