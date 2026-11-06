# Railway — preparação da publicação

Projeto criado (privado): https://railway.com/project/788b8406-d900-4f19-a159-fd7d4ff96338

Ambiente: `production`, ID `4a1b16bf-fd6b-4e12-ba35-1e3824c2adbb`.

| Serviço | Repositório previsto / branch | Domínio reservado |
|---|---|---|
| api | phsilvadev/Atend-hub-backend / development | api-production-5aaf.up.railway.app |
| cliente | phsilvadev/consistent-design-system / development | cliente-production-a80d.up.railway.app |
| superadmin | phsilvadev/super-admin-atendehub / development | superadmin-production-3d47.up.railway.app |

IDs de serviços: API `66fc04cb-4ae4-49fc-b064-10f04110611d`, cliente `3ca8c8fd-e8d3-4978-b9f4-4995277ac315`, superadmin `a5e024d2-c810-495c-9168-50cbbff7a411`. Domínios configurados para porta 8080. PostgreSQL persistente provisionado, deployment SUCCESS. API e os dois Next publicados com SUCCESS por upload direto do CLI. Não confundir serviço/domínio criado com aplicação publicada.

## Configuração da primeira publicação
1. Site Key e Secret Key reais do Turnstile no backend; registrar os hostnames cliente e superadmin acima no widget Cloudflare. APP_ENV=production não aceita dummy keys.
2. Provisionar PostgreSQL persistente, configurar driver/URL, aplicar e validar migrations nele. Não publicar SQLite em disco efêmero. SQLite de desenvolvimento não deve ser enviado como banco inicial nem populado em produção com fixtures.
3. Configurar origens HTTPS explícitas no backend, cookies seguros, chaves de criptografia persistentes e credencial Firebase por mecanismo seguro do serviço. O arquivo de credencial local em /workspace não existe automaticamente no Railway.
4. Associar cada repo/branch correta após configurar as variáveis. Frontends precisam de BACKEND_URL e APP_ORIGIN próprios; comando deve ouvir 0.0.0.0:$PORT. Builder Railpack; nenhum Docker local é necessário.
5. Configurar migrations antes da aplicação iniciar, healthcheck backend /health e validar status terminal SUCCESS/HTTP, cadastro/login/antirrobô, cookies, isolamento e imagem real. Não semear administradores com senhas de demonstração nem planos fictícios em produção.

Nenhuma credencial é registrada neste documento. Preparação não é autorização para desligar o antirrobô, usar chaves de teste em produção ou abrir o Storage publicamente.

## Produção configurada em 06/nov/2026
- Postgres: serviço `4e3fadbf-e974-4caf-90f7-a54b3b1d6ca4`, imagem PostgreSQL 18 com volume persistente; deployment `75226b84-ac0b-4d4e-b78d-52b9a6138c7c` SUCCESS. Sem Docker local.
- API: APP_ENV=production, COOKIE_SECURE=true, DATABASE_URL por referência interna `${{Postgres.DATABASE_URL}}`, psycopg3 e pool_pre_ping. Turnstile real com hostnames cliente/superadmin e modo de teste desligado. Credencial Firebase via variável secreta GOOGLE_SERVICE_ACCOUNT_JSON, bucket e chave de criptografia persistente privada configurados.
- Next: Node 22, APP_ORIGIN próprio, PORT=8080 e BACKEND_URL via rede privada `http://${{api.RAILWAY_PRIVATE_DOMAIN}}:8080`. Build npm run build; start na porta PORT.
- API executa `alembic upgrade head` em pre-deploy, start uvicorn e readiness `/health/ready`, que testa banco e migration head. `/health` é liveness.
- Configuração versionada em railway.toml de cada repo; arquivos locais/segredos excluídos de upload pela .railwayignore e do Git.
- Nenhum usuário ou plano fictício é criado em produção; administrador inicial da plataforma deve ser cadastrado pelo comando protegido existente `python -m app.cli.platform_admin` no ambiente do backend.

## Bloqueio atual da fonte GitHub
A conta foi conectada pelo usuário, mas a API Railway ainda retorna `User does not have access to the repo` para os três repositórios. É necessário autorizar o aplicativo Railway nos repositórios/conta corretos em https://github.com/settings/installations. Não alterar a visibilidade do repositório privado para contornar esse controle. Até resolver, apenas PostgreSQL está com deployment SUCCESS; frontend/API não foram declarados publicados.

Usuário esclareceu que o projeto é compartilhado entre contas: identidades/e-mails diferentes são compatíveis com esse acesso. A diferença de contas, por si só, não comprova a causa do erro e não exige trocar a integração. A integração consegue gerenciar o projeto, porém a vinculação de fonte GitHub continua sendo recusada. Pela conta com a conexão GitHub autorizada, vincular os repositórios aos serviços existentes com branch development; depois a integração poderá acompanhar os deployments. Tentativa de fallback CLI foi cancelada antes do login/envio; nenhuma aplicação publicada.

Inspeção atual: api, cliente e superadmin têm source=null e latestDeployment=null; não existe mudança staged para aplicar. PostgreSQL continua SUCCESS. Não recriar serviços/projeto nem alterar visibilidade dos repositórios. Falta o primeiro vínculo de fonte pelo membro com acesso GitHub autorizado.

## Publicado — upload direto pelo CLI
A conta com créditos é cashewdevops@gmail.com. Foi autenticada via device code e o código local enviado aos serviços existentes. Esse método dispensa permissão GitHub e não cria outro projeto. Os recursos anteriores e as variáveis privadas foram reutilizados.

| Serviço | Deployment com SUCCESS | Endereço |
|---|---|---|
| api | fb2f22db-806d-42b0-825b-0648a27617d3 | https://api-production-5aaf.up.railway.app/health/ready |
| cliente | 19f40c1c-30af-40b4-8f61-b7093cd9247d | https://cliente-production-a80d.up.railway.app/login |
| superadmin | a9866479-58a1-40ea-a2bc-443a307220dd | https://superadmin-production-3d47.up.railway.app/login |

Atualizações futuras pelo diretório de cada repositório:
```bash
railway login
railway up --project 788b8406-d900-4f19-a159-fd7d4ff96338 --environment 4a1b16bf-fd6b-4e12-ba35-1e3824c2adbb --service <ID_DO_SERVICO> --detach -m "Descrição da atualização"
```
Aguardar status SUCCESS antes de declarar publicação. Push no GitHub sozinho ainda não dispara deployment: nenhuma fonte GitHub foi vinculada. A .railwayignore e o Git excluem .env, dados locais e credenciais; segredos são variáveis do serviço.

Validação pública: páginas e BFFs HTTP 200; API readiness PostgreSQL/head OK. Turnstile enabled=true/testing=false nos dois painéis; token ausente e Origin não permitido recusados com 403/sem sessão. Widget real renderizado nos três formulários aguardando confirmação humana; não automatizar/burlar o desafio nem alegar login completo já validado. Prints desktop/mobile gerados sem overflow. Dados comerciais fictícios não foram inseridos no banco de produção. Cadastro inicial do superadministrador aguarda definição do e-mail.

Firebase foi verificado com as variáveis reais do serviço em um processo local via railway run --no-local (bucket acessível); isso não representa execução remota por SSH. Nenhuma chave SSH foi cadastrada. O CLI avisou depreciação do railway.toml para 01/dez/2026: planejar migração para IaC antes do prazo, sem bloquear este deploy atual.

## Gateway QR publicado

Serviço `whatsapp-qr` (`f4530345-0cc1-40f8-866f-0256cd7fd956`), pasta `whatsapp-bridge` enviada como raiz via CLI, Node 22, uma instância e volume persistente de 500 MB em `/data`. Healthcheck `/health`, bind `0.0.0.0:8300`, estado em `/data/state`. Domínio HTTPS: `whatsapp-qr-production-9a4f.up.railway.app`. Rotas de sessão exigem Bearer; navegador usa exclusivamente BFF/API, sem receber token do gateway. API configurada com URL/token e callback HMAC validado. A chave AES não deve ser trocada a cada deploy. Repetir upload dessa pasta para atualizar o gateway, não o upload da raiz Python.

Em 06/nov/2026, gateway e API com deployments SUCCESS; QR real gerado e sessão de teste removida sem parear celular. Pareamento pelo usuário e envio/recebimento real ainda precisam ser validados.
