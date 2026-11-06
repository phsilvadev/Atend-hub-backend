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

### Frontend próprio do superadministrador
O projeto separado `/workspace/super-admin-atendehub` foi migrado para Next.js e integra login de plataforma e listagem somente leitura em `GET /api/v1/platform/companies`. Não utiliza o login das distribuidoras. Origem local padrão: http://localhost:3001 (adicionada aos exemplos/defaults de desenvolvimento, preservando localhost:3000). Em produção, configurar origens HTTPS explícitas como antes. Cadastro/edição de empresas e integração dos demais módulos do superadmin permanecem pendentes.

## WhatsApp — recebimento de texto (Fase 03 parcial)

Configure `WHATSAPP_APP_SECRET` e `WHATSAPP_VERIFY_TOKEN` no ambiente do servidor/gerenciador de segredos. Nenhum token de acesso Meta é necessário para apenas validar/receber webhooks. O segredo é do app Meta SaaS; cada número operacional pertence a uma distribuidora. Não há WhatsApp global para atendimento da plataforma.

```bash
.venv/bin/alembic upgrade head
.venv/bin/python -m app.cli.whatsapp_number --company-id UUID_DA_EMPRESA --phone-number-id ID_DO_NUMERO_META --waba-id ID_DA_CONTA_WHATSAPP
```

Execute o vínculo somente após verificar a titularidade/autorização do número no app Meta. A CLI é administrativa, idempotente e recusa transferências de um número entre empresas. Não existe endpoint público para escolher tenant ou vincular números arbitrários. A tela de conexão no painel do cliente ainda está pendente.

No painel Meta configure o callback `https://SEU_BACKEND/api/v1/webhooks/whatsapp`, o verify token e a assinatura do campo `messages` para as contas autorizadas. Exponha somente via HTTPS e aplique limite de requisições na borda. O webhook valida `X-Hub-Signature-256` contra os bytes originais antes de interpretar JSON. Segredos não são persistidos no SQLite nem enviados ao frontend.

Texto recebido cria cliente por telefone e atendimento WhatsApp `new`, ou reutiliza o atendimento WhatsApp aberto. Fechado/convertido gera novo atendimento. Preserva responsável/status humano existentes. Empresa inativa/trial vencido e vínculo desativado não recebem novos registros. WABA e phone_number_id precisam corresponder ao vínculo confiável. IDs externos ficam vinculados às mensagens e deduplicados por número, inclusive em reentregas concorrentes.

Neste recorte, o processamento é **síncrono e transacional**, com retorno 200 somente após commit. Falha de banco retorna erro para retry da Meta; rollback impede gravação parcial. Não há Redis/Celery, retentativas próprias ou fila persistente nesta etapa. Eventos de status e mídias não são processados; a Meta recebe 200 para esses tipos sem registro. Ordenação do histórico usa recebimento/ID local; timestamp externo fica no horário da mensagem. Nenhuma resposta é enviada e nenhuma IA é executada; mensagens manuais continuam sendo registros locais.

Sem credenciais/conta Meta e callback público, a ativação externa permanece pendente. Os testes usam apenas app/números fictícios em SQLite temporário. Nenhum Docker foi executado.

Referência oficial consultada: [webhooks — documentação hospedada pela Meta](https://whatsapp.github.io/WhatsApp-Nodejs-SDK/api-reference/webhooks/start/). O SDK está arquivado e não é utilizado; a página confirma challenge e assinatura. A documentação atual em developers.facebook.com retornou HTTP 429 durante a consulta; revalidar onboarding/conta e configurações atuais antes da ativação real. Não há chamadas de envio nem endpoints Graph inventados.

## WhatsApp não oficial por QR Code

Por solicitação explícita do usuário, existe uma segunda opção independente da conexão oficial: gateway Baileys em [whatsapp-bridge](whatsapp-bridge/README.md). O administrador da distribuidora abre **Integrações → WhatsApp por QR Code → Conectar WhatsApp**, e faz a leitura em Dispositivos conectados no celular. Não é necessário preencher número/token Meta no navegador.

1. Execute `alembic upgrade head` e configure `WHATSAPP_QR_BRIDGE_URL` e `WHATSAPP_QR_BRIDGE_TOKEN` somente na API.
2. Instale/execute o gateway Node conforme seu README, com token correspondente e chave própria de criptografia. Não há Docker nesta execução.
3. Inicie a API e o frontend. Cada empresa recebe sua própria sessão; apenas admin ativo com trial válido pode obter o QR ou desconectar.

Se gateway/token não estiver configurado, o painel informa que a ativação está pendente e mantém o botão desabilitado. Erros de comunicação não são exibidos como conexão bem-sucedida. A conexão oficial continua disponível separadamente no backend; seu onboarding simplificado não foi implementado.

Novos textos recebidos pelo gateway entram no canal `whatsapp_qr`, seguindo isolamento, deduplicação e regras da central. Desconectar bloqueia callbacks imediatamente e preserva histórico; reconectar após desconexão cria nova sessão. Envio continua registro local, sem transporte de saída. Geração do QR real foi validada até o navegador; pareamento, recebimento e restauração com conta/celular real ficam pendentes; a integração não oficial pode precisar de novo pareamento conforme alterações do WhatsApp. A versão de biblioteca está fixada no lockfile e requer manutenção do fornecedor.

## Cadastro seguro do WhatsApp oficial por empresa

O administrador configura **Integrações → WhatsApp Business → Conectar**: Phone Number ID, WABA ID e token de acesso. O servidor valida o vínculo número/conta na Graph API da Meta antes de salvar. Não marca o canal como conectado apenas por salvar as credenciais. Após validar, o aside se expande para 960px e mostra aplicativo, registro do número, inscrição WABA e recebimento pelo webhook.

### Proteção dos segredos

- Token criptografado com **AES-256-GCM**, nonce aleatório e contexto autenticado da empresa/número/WABA. Copiar o ciphertext para outra empresa ou alterar IDs não permite decifrá-lo.
- A chave `WHATSAPP_CREDENTIAL_KEY` tem 32 bytes aleatórios em base64 e **não fica no banco**. Em produção, use o gerenciador de segredos da hospedagem; preserve a chave e seus backups separadamente dos backups SQL. Perdê-la exige cadastrar novos tokens. Não há rotação automática nesta entrega.
- Somente administradores de empresa ativa/trial válido podem ler metadados, trocar credenciais e iniciar ativação. API nunca devolve token, ciphertext, App Secret ou chave. O campo de token permanece vazio ao reabrir; deixe-o vazio para manter a credencial salva, ou forneça novo token para alterar os IDs.
- O navegador usa input password, sem localStorage/sessionStorage. O valor informado é enviado apenas no salvamento e limpo após submissão/fechamento. O transporte público deve usar HTTPS, inclusive entre BFF/API remotos. Não é possível esconder do próprio administrador o token que ele mesmo está enviando pelo navegador.
- Erros e auditoria não contêm tokens/PIN. Logs verbosos de httpx são desabilitados e httpcore fica em WARNING porque `debug_token` da Meta exige o token na query HTTPS. Na hospedagem/APM, também desabilite captura de corpos/Authorization/query `input_token`; não configure logs de payloads sensíveis.
- Remover conexão apaga o ciphertext e bloqueia novas importações deste número. Não revoga o token na Meta nem remove inscrições WABA compartilhadas; essa decisão deve ser feita pelo responsável no aplicativo Meta.

Inicialização local de desenvolvimento (sem imprimir o segredo):

```bash
.venv/bin/python -m app.cli.integration_key
.venv/bin/alembic upgrade head
# Reinicie a API para carregar a chave da .env ignorada pelo Git.
```

A CLI não sobrescreve chave existente e é bloqueada em produção. Não copie chaves de testes para produção, não versione `.env` e não use NEXT_PUBLIC para segredos.

### Requisitos da Meta e ações de ativação

1. Tenha conta WABA, número autorizado/verificado para Cloud API e token de usuário do sistema com acessos aos ativos necessários. Validação requer `whatsapp_business_management`; registro requer também `whatsapp_business_messaging`.
2. Configure na plataforma `WHATSAPP_APP_ID`, `WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN` e `WHATSAPP_PUBLIC_WEBHOOK_URL`. O token do cliente deve pertencer ao aplicativo SaaS autorizado. App Secret/verify token são parâmetros da plataforma, não campos expostos ao cliente.
3. Valide no painel Meta o callback HTTPS e a assinatura do campo **messages** do objeto WhatsApp Business Account. A configuração global/verificação do callback exige configuração real na Meta e não é considerada pronta só por haver uma URL no ambiente.
4. **Validar e salvar** confirma número/WABA, e, quando o App ID/Secret estão configurados, validade, aplicativo emissor, permissões/expiração, situação de registro e inscrição do aplicativo. Sem configuração do aplicativo, a credencial pode ser salva como validada para leitura, mas as operações de ativação ficam bloqueadas e a pendência aparece no painel.
5. Se o número ainda não estiver registrado, informe o PIN de seis dígitos e confirme **Registrar na Cloud API**. PIN não é código SMS, não é gerado arbitrariamente, não é salvo e só é usado nessa chamada. Não registra novamente número já CONNECTED e não migra automaticamente um número On-Premises.
6. Confirme **Ativar recebimento de eventos** para inscrever o aplicativo na WABA. A API verifica o App ID antes dessa alteração. A inscrição não configura automaticamente o callback global nem o campo messages no painel Meta.
7. Envie uma mensagem real ao número e use **Atualizar situação**. Só um evento assinado e persistido comprova o recebimento na central; campo `status=CONNECTED` da Meta indica registro do número, não valida nosso fluxo inteiro.

O PIN e o registro/inscrição são operações explícitas com confirmação, nunca efeitos colaterais do salvamento. Tokens expirados/revogados exigem atualização e nova validação; não há renovação automática. Envio de mensagens, janelas de atendimento, templates e cobrança continuam nas fases seguintes.

Documentação consultada: [coleção oficial Meta — WhatsApp Cloud API](https://www.postman.com/meta/whatsapp-business-platform/documentation/wlk6lh4/whatsapp-cloud-api), endpoints phone_numbers, debug_token, subscribed_apps e register. Graph API fixada em v25.0 (configurável por ambiente); host fixo graph.facebook.com, sem redirects e sem seguir URLs de paginação externas. As chamadas são verificadas em testes com transport HTTP simulado; validação de conta/token real e configuração na Meta permanecem bloqueadas pela ausência de credenciais reais.

## GestãoClick — cadastro essencial (sem transporte ERP)

O card GestãoClick em Integrações permite ao admin cadastrar, editar e remover endereço base HTTPS (`/api` ou `/v1`), Access Token e Secret Access Token. Este recorte **não valida acesso ao ERP, não chama endpoints externos e não sincroniza dados**. O status é `Credenciais cadastradas`, nunca Conectado.

O par de credenciais é cifrado com AES-256-GCM, nonce aleatório e contexto próprio GestãoClick/empresa/URL, usando a chave de servidor já existente `WHATSAPP_CREDENTIAL_KEY`. A chave continua fora do SQL. Inicialize-a com `python -m app.cli.integration_key` em desenvolvimento; em produção use um gerenciador de segredos e HTTPS. Os campos nunca retornam da API. Campo omitido mantém seu valor salvo; trocar a URL exige os dois tokens novos. Remover apaga o ciphertext, não revoga a chave no ERP.

Aplicar migrations com `alembic upgrade head`. Teste direcionado: `pytest -q tests/test_gestaoclick.py`. A validação do servidor/conta, proteção de resolução DNS/SSRF para futuras chamadas, seleção de loja, limites de acesso e sincronização dependem do OpenAPI da conta e ficam pendentes. A URL hoje tem apenas validação de formato; nenhuma conexão é feita para ela. Não foram inseridas credenciais fictícias no banco local: dados fictícios são usados apenas em testes temporários.

## Atualização: GestãoClick — testar acesso e selecionar loja

Baseado no OpenAPI 3.1 enviado pelo usuário: [contrato e decisões](docs/GESTAOCLICK_ACCESS.md). Depois do cadastro seguro, o admin pode clicar em **Testar conexão**, consultar `GET https://api.gestaoclick.com/api/lojas` com os dois headers e escolher uma loja retornada. O backend usa apenas o servidor fixo confirmado; nunca envia tokens a um endereço arbitrário, não segue redirects e não coloca tokens na URL.

O resultado é **Acesso às lojas validado**, não integração completa. A permissão `Lojas/index` foi verificada pela chamada, mas produtos/clientes/preços/estoque e o usuário efetivo da chave ainda precisam de validação. Campos `stores`, `selected_store_id`, `tested_at` e `test_error_code` são persistidos e isolados por empresa. Mudança de credenciais invalida o teste; falhas limpam lojas/seleção anteriores. Seleção precisa constar no último teste bem-sucedido, com até 15 minutos.

A API documenta erros 401/402/403/429 e quota de 3/s e 30.000/dia por empresa ERP. O teste tem limite local mais restrito (1/s e 10/15min por tenant), timeout e respostas limitadas. Erros retornam mensagens próprias, sem tokens ou payloads brutos. Em falha não há logout da conta SaaS. Loja selecionada é uma preferência: vínculos fixos da chave no ERP podem prevalecer nas futuras consultas de catálogo.

Aplicar `alembic upgrade head`. Testes: `pytest -q tests/test_gestaoclick_access.py tests/test_gestaoclick.py`. Para testar uma conta real, cadastre credenciais autorizadas pelo painel e use o servidor indicado no OpenAPI. Não foram usados tokens reais nesta entrega; as validações automáticas simulam o transporte HTTP do ERP, mantendo API/SQL reais. Não há sincronização, gravação de documentos no ERP ou consumo OpenAI nesta etapa. A prévia frontend continua isolada e explicitamente simulada.

### Sincronização essencial de produtos
Em Integrações → GestãoClick, teste o acesso, salve a loja e clique em **Sincronizar produtos**. O painel mostra progresso e último sucesso; **Produtos** agora consulta o banco, com busca/paginação e sem amostras fixas. Fechar/recarregar pausa o processamento; use **Continuar sincronização**. Importações incompletas preservam o catálogo anterior. Apenas leitura no ERP, sem preços/estoque/unidade/variações detalhadas e sem exclusões. Limites: 10.000 produtos/100 páginas por execução. Contrato extraído em `docs/contracts/gestaoclick-products.openapi.json`; cobertura em `tests/test_product_sync.py`.
