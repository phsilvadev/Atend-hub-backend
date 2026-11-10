# Arquitetura — Backend AtendeHub

API FastAPI com SQLAlchemy 2 e migrations Alembic. Camadas: `app/api` (rotas e dependências), `schemas` (contratos), `services` (autenticação e transações), `repositories` (consultas filtradas por tenant), `models` (ORM) e `core` (configuração, banco e segurança).

SQLite em desenvolvimento/testes. Tabelas: companies, users, sessions, audit_events e auth_attempts. O cadastro cria empresa, administrador e sessão atomicamente. O trial começa no servidor e dura 604800 segundos; novos logins não o renovam.

Cookies opacos HttpOnly/SameSite=Lax, Secure em produção. Apenas hashes SHA-256 dos tokens aleatórios são persistidos; senhas usam Argon2. Toda sessão vincula empresa e usuário. Ativação de ambos é verificada a cada acesso. E-mail é único globalmente nesta fase: cada identidade pertence a uma empresa.

As rotas operacionais obtêm o tenant da sessão e filtram por ele; IDs do cliente não concedem acesso. Somente admin administra usuários da própria empresa. Trial vencido permite me/logout, bloqueando operações operacionais. AuditEvent possui empresa e ator; AuthAttempt é infraestrutura global anterior à autenticação e armazena chaves hash e horários para controle de tentativas.

Mutações validam Origin/Referer permitido. A API não habilita CORS amplo; o frontend Next utiliza proxy de mesma origem. Sem tokens em JSON/localStorage, senhas em logs ou seeds de produção. Limites persistidos por IP/e-mail devem ser complementados na borda antes de produção.

Não há create_all no startup: aplique migrations explicitamente. Pytest cria SQLite temporário via migrations e valida isolamento, autenticação e reversão do esquema.

Produção e demais módulos estão pendentes no CHECKLIST.md. Nenhum Docker é necessário. Frontend e seus testes estão no repositório AtendeHub, fora deste backend independente.

## Perfil da empresa e horários
`CompanyProfile` possui chave primária/FK `company_id` (relação 1:1 com Company), campos de contato/endereço e JSON com sete dias de atendimento. O nome fantasia continua em `Company.name`, preservando os contratos de autenticação e cabeçalho. Schema Pydantic valida CNPJ (inclusive alfanumérico), contato, CEP, UF, fuso IANA e faixas de horário. `app/services/company.py` lê e grava exclusivamente a empresa do contexto autenticado. GET exige tenant ativo; PATCH exige administrador, atualiza nome/perfil em uma transação e registra auditoria sem copiar informações pessoais. A migration aditiva não preenche dados fictícios. Os horários não executam automações nesta fase.

## Catálogo de planos e consulta da assinatura
A tabela `plans` é um catálogo global da plataforma (não operacional de um tenant), com preço em centavos, moeda, limite informativo, recursos JSON, ordem, ativação e marcador de demonstração. A empresa mantém o código contratado em `Company.plan`; a nova API é somente leitura e nunca modifica esse código. Datas de trial e contagens de usuários vêm do banco com filtro pela empresa da sessão. O seed é explícito, idempotente e bloqueado em produção; itens demo também são excluídos das respostas de produção. Checkout, assinatura financeira, entitlements e aplicação de cotas continuam pendentes. O frontend consome o contrato da API e valida o company_id retornado. O skeleton não utiliza valores substitutos de plano.

## Central manual — Fase 02 parcial
`Customer`, `Conversation` e `ConversationMessage` ficam em `app/models/conversations.py`. Cliente possui telefone único por empresa. Conversa referencia cliente e responsável com FKs compostas incluindo company_id; mensagens referenciam conversa/ator também pelo par id/tenant. O próprio banco impede relações cruzadas. O cadastro de cliente é mínimo nesta etapa, sem implementar o CRM completo.

A camada de repositório aplica escopo do tenant e propriedade (admin/supervisor: empresa inteira; seller/operator: próprio ou livre). Serviços validam atribuição, controle de versão e estados antes de escrever. Rotas delegam regras de negócio aos serviços. Atualizações e mensagens usam compare-and-swap e transações; request_id único e hash do corpo de criação protegem retries. Contatos existentes são reutilizados sem sobrescrita. Histórico tem paginação por ID e eventos de sistema para criação, atribuição e transições. Auditoria registra ações sem o conteúdo privado das mensagens.

A interface mantém o funil e o painel lateral, usa estados de carregamento/erro/vazio, consulta o backend e não inicializa conversas fictícias. O protótipo visual anterior está arquivado em `components/atendimentos/demo`, sem importação nas rotas. O proxy Next encaminha query strings validadas pela API para busca/paginação. IA, WhatsApp, automação de horário, WebSocket/SSE e SLA comercial continuam pendentes; leitura e atualização por polling foram entregues na etapa seguinte descrita abaixo. O canal manual registra textos somente na central; não possui transporte externo.

## Leitura por usuário e atualização automática
`ConversationRead` possui PK company_id/conversation_id/user_id e FKs compostas para conversa e usuário do mesmo tenant. Um único cursor por pessoa/conversa avança via UPDATE com CASE; inserções concorrentes usam savepoint/unique constraint e nova tentativa. O corpo da API nunca escolhe o usuário. Contagens agregadas excluem sistema e o próprio ator e aplicam o mesmo predicado de visibilidade da central. Leituras não alteram a versão comercial nem a ordenação dos cards.

A API de updates é incremental por ID, autenticada e limitada. No cliente, `useVisiblePolling` pausa em segundo plano, retoma no foco e impede ciclos sobrepostos. Respostas antigas são descartadas após mudanças de seleção/filtro ou operações manuais; novidades se mesclam ao histórico preservando rascunho e paginação. O cursor de leitura usa o último ID exibido com a aba visível e o fim do histórico em acompanhamento. Transferência que remove a autorização resulta em 404 e limpa os dados do painel; não expõe o novo responsável ao vendedor anterior. Falhas 401/403 limpam o conteúdo e revalidam a sessão.

`first_response_at`, `handling_seconds` acumulado e `opened_at` persistem as métricas manuais. Encerramento/conversão pausam e reabertura retoma o período; não são métricas de entrega WhatsApp nem de expediente comercial. A migration tem backfill de histórico existente e downgrade/upgrade testado sem perder mensagens. Testes concorrentes usam threads e sessões reais para disputar atribuição, repetir uma mensagem e confirmar leituras fora de ordem. Testes E2E usam duas sessões independentes para atualização, rascunho, leitura e revogação por transferência.

## Domínio global da plataforma e conhecimento comum
A identidade de plataforma é separada de User/Company: PlatformAdmin, PlatformSession e PlatformAudit não possuem tenant porque representam a administração global, não registros operacionais de distribuidora. Não há flag/role de tenant que conceda esse privilégio. Provisionamento é local por CLI, login com Argon2/rate limiting/CSRF e cookie próprio de uma hora. A sessão da plataforma não autentica nas rotas operacionais de tenants.

KnowledgeImport, KnowledgeEntry, KnowledgeRevision e KnowledgeApproval formam exclusivamente a biblioteca global curada. Só administradores da plataforma acessam material importado/revisões pendentes. Entradas tenant-private não são armazenadas nessas tabelas. A biblioteca é consumida em rotas autenticadas de empresa que filtram active/published_revision, sem conceder acesso à gestão ou importações. Edição cria revisão; publicação avança o ponteiro aprovado com CAS e registro de confirmação humana; uma edição pendente mantém a revisão aprovada anterior. Desativar remove a entrada da consulta pública autenticada.

A importação limita o corpo antes do parsing, exige fonte autorizada, redige padrões/termos conhecidos e persiste só o material tratado. O original não é salvo; hash serve para retries. Extração de pares adjacentes não usa LLM e nunca publica automaticamente. Os padrões são assistivos: revisão humana de privacidade, direitos e validade técnica é obrigatória. O WhatsApp operacional e o GestãoClick pertencem a cada empresa; não há conexão WhatsApp global nem leitura automática das conversas existentes. Fonte comum genérica e dados comerciais oficiais/privados são domínios diferentes. Plano do painel da plataforma e limitações constam em docs/PLATFORM_KNOWLEDGE.md.

## Consulta global de empresas pelo superadmin
O frontend separado super-admin-atendehub usa Next.js e sessão de plataforma validada no middleware/proxy, layout e API. O BFF aceita apenas autenticação e GET companies; ignora cookies de tenant e reescreve o Path do cookie próprio para proteger páginas. A API permite ler metadados de empresas (com auditoria), sem conceder sessão de tenant, acesso a conversas, edição ou impersonação. A listagem é paginada e possui filtros reais. O painel de conhecimento e demais módulos permanecem pendentes no novo frontend.

## WhatsApp inbound — recorte da Fase 03

API `app/api/whatsapp.py` autentica evento via HMAC antes do parser e chama serviço `app/services/whatsapp.py` em threadpool. Única exceção ao CSRF por Origin é o POST do webhook, protegido por assinatura. Configuração SecretStr vem do ambiente do servidor. O app Meta é da plataforma SaaS; `whatsapp_numbers` vincula WABA/phone_number_id a cada tenant e não armazena segredo. A CLI administrativa não permite transferir vínculo entre tenants.

Processamento local síncrono, transação única por webhook. Atualização atômica do vínculo serializa concorrência por número no SQLite e PostgreSQL; recibo composto número/ID externo deduplica e referencia a mensagem. Criar cliente/atendimento/mensagem/recibo é atômico; falhas retornam erro e permitem retry externo. Atualização de conversa incrementa versão para invalidar edições humanas obsoletas. Nunca atribui IA nem altera responsável humano. Futuro worker/fila e transporte de saída ficam em etapa separada; PostgreSQL não foi validado nesta entrega.

## Provedor não oficial por QR Code

Autorizado explicitamente após o escopo originalmente exclusivo da API oficial. Gateway Node/Baileys separado em whatsapp-bridge; não roda dentro do Next.js. API FastAPI chama gateway privado por Bearer e deriva a sessão exclusivamente do contexto autenticado. Credenciais Signal e outbox ficam criptografadas AES-GCM no gateway; QR temporário somente em memória e respostas no-store. Frontend usa BFF com allowlist de três rotas; callback não é exposto no BFF.

`whatsapp_qr_connections` possui uma sessão por company_id e ID único. Alias interno `qr-{uuid}` em whatsapp_numbers mantém recibos existentes, com WABA interna qr; canal separado whatsapp_qr evita misturar conversa oficial e sessão pareada. Eventos internos assinados e recentes passam por validação e consultam a sessão ativa antes de reutilizar o processamento transacional de entrada. Desconexão desativa o alias antes do logout remoto; novo pareamento após desconexão troca UUID. Nenhum token/sessão é escolhido pelo browser.

Gateway é um processo único por diretório, com reconexão limitada, restauração de auth criptografado e outbox persistente com retry. Não substitui fila distribuída e não importa histórico; não há garantia de captura durante downtime. Monitoramento, quotas/retenção da outbox e validação de pareamento real permanecem pendentes de produção.

## Credenciais oficiais e ativação

Nova tabela whatsapp_official_connections vinculada a company_id e phone_number_id já existente. Token em AES-GCM (nonce 12 bytes, chave 256 bits em ambiente externo ao SQL, AAD company/phone/WABA); metadados de validação em JSON sem segredos. Uma conexão oficial por tenant; troca de número desativa o anterior, números não são transferidos entre empresas. Versionamento evita sobrescrita concorrente; autorização administrativa é revalidada após I/O externo antes de persistir. Rotas de setup serializam operações locais por empresa; não é transação distribuída com Meta.

Adaptador Meta com host e paths controlados, Authorization no header, prazo total limitado, redirects recusados, paginação por cursor sem seguir URL. debug_token usa App access token no header para conferir emissor/scopes/expiração; sua query sensível não deve entrar em logs/APM. httpx logs suprimidos, httpcore WARNING e erros locais sanitizados. Dados técnicos desconhecidos não são inferidos como sucesso.

Cadastro de credenciais é separado de registro do número e inscrição WABA. Alterações externas exigem confirm:true e controles de permissões/versão; PIN transitório. Callback global/App Secret/verify token permanecem configuração da plataforma. Só webhook assinado/persistido comprova recepção; número CONNECTED ou inscrição confirmada isoladamente não demonstram fluxo completo. Sem tokens reais não há validação de produção, registro real, assinatura real de aplicativo ou envio a clientes.

## GestãoClick — configuração sem integração externa

Tabela gestaoclick_connections com PK company_id, URL normalizada, par de tokens cifrado, versão e data. AAD específico `atendehub:gestaoclick:v1:{company_id}:{url}` impede troca do ciphertext entre tenants/endereços e entre provedores. Reusa a chave AES-256 existente do backend, sem modificar o formato de credenciais WhatsApp. Não há transporte HTTP ERP, fila ou sincronização neste recorte; nenhuma URL fornecida é acessada. Antes de implementar transporte, validar domínio do servidor contra OpenAPI e aplicar proteção DNS/SSRF/redirects, permissões e limites reais.

## GestãoClick — adaptador restrito de acesso

`app/integrations/gestaoclick.py` encapsula um único GET /lojas do OpenAPI fornecido, com servidor fixo HTTPS, headers privados, redirect bloqueado, timeout e limite de 1 MiB/1000 lojas. Não há host fornecido pelo cliente no transporte. Modelo ganha cache autorizado de lojas, teste/data/erro, início da tentativa e seleção. Versão e reautorização após I/O impedem aplicar resultado obsoleto a credenciais alteradas ou acesso revogado. A chamada externa ocorre sem lock de escrita; alterações finais são serializadas por empresa.

A seleção é validada contra o cache do tenant, sem inferir permissão de catálogo. Não há fila, sincronização ou escrita ERP. O OpenAPI inclui outros servidores (CRM/assinatura digital), intencionalmente fora da allowlist deste recorte. Contrato mínimo e hash do arquivo recebido estão em docs/contracts e docs/GESTAOCLICK_ACCESS.md. Em testes, só o transporte ERP é simulado; autenticação, criptografia, API e banco continuam reais.

### Importação essencial de produtos
O catálogo é tenant-scoped e alimentado por adapter GET documentado. `product_syncs` mantém uma execução por empresa; `product_sync_items` é staging privado e temporário, descartado em falhas/reinício. Lease no banco impede páginas concorrentes; chamadas não mantêm lock de escrita durante I/O. Antes de publicar, a API revalida sessão, papel, empresa e versão da integração. O catálogo só muda numa transação após concluir e conferir todas as páginas, sem exclusão dos produtos ausentes. O cliente dirige a execução página a página; fechamento pausa e nova visita permite continuar. Não há promessa de execução autônoma em background. URLs de próxima página retornadas pelo ERP são ignoradas: endereço fixo confirmado e paginação numérica local.

### Imagens próprias do catálogo
`product_images` separa rotas/autorização, sanitização via Pillow e adapter Firebase Admin SDK. O browser utiliza uma rota binária específica do Next com validação de Origin e limite de 5 MiB, mantendo o BFF JSON existente. O banco armazena referência privada/generation e versão por produto. Upload usa chave imutável gerada pelo servidor, revalidação de acesso e controle otimista antes de associar a imagem; substituição tenta excluir o objeto anterior após commit. Não há transação distribuída com o Storage: órfãos após interrupção/exclusão com falha requerem reconciliação operacional. Leitura autenticada por tenant evita bucket público ou tokens de download duradouros. Fotos não dependem do contrato GestãoClick e não são alteradas pelo importador ERP.

### Antirrobô antes da autenticação
`services/turnstile.py` concentra a integração fixa com Cloudflare Siteverify e a validação de contexto. Os endpoints cliente/plataforma aplicam limites antes do serviço e só criam sessões/empresas após sucesso. Migração `20261106_turnstile` adiciona fingerprints de token com expiração e unicidade para replay. Ambos os Next consultam configuração pública via BFF e renderizam widget explícito, renovado a cada tentativa; token fica somente em memória. Configuração de produção falha sem chaves reais/hostnames, sem aceitar modo de teste. Segredo é exclusivo do backend.

### Autorização Meta via Cadastro Incorporado

SDK no cliente envia código temporário e IDs para o BFF autenticado. A API controla tentativas de cinco minutos vinculadas à sessão/empresa/usuário/versão; fingerprints de estado/código persistidos, consumo atômico, recusa de replay. Troca de código no host fixo Meta e token AES-GCM usam validação existente, com diagnóstico separado das ações explícitas de registro/inscrição. Não há endpoint público de callback OAuth da aplicação; o código vem do callback do SDK. Configuração e limitações: docs/WHATSAPP_EMBEDDED_SIGNUP.md.

### Identidade Google e recuperação do cliente

Google Identity Services no frontend entrega ID token com nonce; BFF encaminha cookie HttpOnly de fluxo e token para verificação google-auth no servidor. Estado descartável e vínculo por subject em tabelas próprias; sessão operacional e regras de tenant existentes são reutilizadas. Recuperação SMTP usa hash de token/versionamento de senha, link em fragmento, consumo atômico e revogação de todas as sessões. Envio por tarefa em processo, sem fila durável nesta etapa. Detalhes em docs/CLIENT_AUTH.md.

### Identidade primária e configurações OpenAI
`platform_control` fixa o primeiro administrador e coordena mutações administrativas por atualização condicional de versão. A escolha é feita no provisionamento inicial ou na migração da identidade existente; não vem do frontend. Confirmação de senha e sessão ativa são verificadas sob a coordenação; a versão individual evita sobrescrita de edições concorrentes. Login usa comparação condicional do hash vigente antes de criar sessão, evitando sessão nova após validação de senha já rotacionada.

`platform_openai` contém configuração versionada, ciphertext AES-256-GCM com AAD próprio e diagnóstico sem segredos. Chave mestra em variável protegida separada da chave OpenAI. O adaptador acessa apenas host oficial fixo, sem redirects ou URL configurável, com timeout e classificação de falhas. Não implementa geração nem usa a biblioteca de conhecimento automaticamente. O diagnóstico libera o bloqueio antes da chamada externa e revalida ator/sessão/versão ao persistir o resultado.

### Suporte da plataforma
`support_threads` usa chave composta empresa/usuário e FK composta para users; um lease guarda o envio em andamento. `support_turns` registra pergunta redigida, resposta, fontes versionadas, status, modelo/versão de configuração e uso informado pelo provedor. A unicidade (empresa, usuário, request_id) dá idempotência. `support_quotas` reserva limites diários em ordem fixa global→empresa→usuário na mesma transação. A reserva e o envio são confirmados antes do HTTP; não se mantém lock durante a geração. Finalização revalida sessão, vínculo, trial, configuração e posse do lease. Falhas não são reenviadas automaticamente; leitura/replay após reinício não repete chamadas cobradas.

Fontes de suporte em código são separadas da biblioteca comum de ferro e aço e de conteúdo comercial privado. O modelo não recebe IDs, nomes de empresas ou ferramentas. Redação assistida e contexto limitado minimizam exposição; não equivalem a anonimização garantida. `store=false` evita persistência intencional de Responses; política do provedor continua aplicável. Limpeza oportunística e CLI disponíveis; agendamento dedicado permanece pendente; o painel agregado e o livro durável foram implementados conforme seção Livro de consumo e tarifas de IA.

### Livro de consumo e tarifas de IA
`ai_usage` registra tentativas de geração por ID idempotente, com FK composta usuário/empresa e sem conteúdo de mensagens. O início é persistido na mesma transação da reserva do suporte; a finalização inclui medições mesmo quando a resposta não pode ser exibida. Não depende da retenção do chat. O helper `ai_accounting` deve ser usado pelas futuras integrações de geração; hoje o único fluxo gerador implementado é suporte. GET de diagnóstico não é uma geração.

`ai_prices` mantém versões por modelo/vigência com fonte oficial e taxas USD/1M. O livro fixa a tarifa conhecida na chamada; modelo resolvido e modalidade são considerados. Alterações posteriores não sobrescrevem custos calculados. Cadastro e aplicação explícita a pendências usam reautenticação e coordenação de mutações administrativas; não executam chamadas cobradas. Decimal evita cálculo financeiro com floats em Python; PostgreSQL NUMERIC preserva os valores em produção. A visão agregada expõe cobertura, pendências e subtotal para não esconder gastos desconhecidos. Não há reconciliação com fatura do provedor, câmbio, taxes, descontos ou consumo externo nesta etapa.
