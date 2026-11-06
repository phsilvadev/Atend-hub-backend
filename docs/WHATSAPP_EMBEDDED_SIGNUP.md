# Conectar com a Meta — Cadastro Incorporado

Implementação do fluxo oficial padrão de um WABA/número, com Facebook SDK para JavaScript. Não implementa coexistência com o aplicativo Business, migração On-Premises ou onboarding multi-WABA. Configuração manual preservada como alternativa.

## Fontes oficiais consultadas em 06/11/2026

- Implementação e eventos do SDK: https://developers.facebook.com/docs/whatsapp/embedded-signup/implementation/
- Onboarding como Tech Provider e troca de código no servidor: https://developers.facebook.com/documentation/business-messaging/whatsapp/embedded-signup/onboarding-customers-as-a-tech-provider/

A documentação confirma `FB.login` com `config_id`, `response_type: code`, `override_default_response_type: true` e `extras.setup`. O callback retorna código temporário e o evento `WA_EMBEDDED_SIGNUP`/`FINISH` informa WABA/número. O servidor chama `GET /{version}/oauth/access_token` no host fixo graph.facebook.com, com client_id, client_secret e code. A versão vem de WHATSAPP_GRAPH_VERSION; não copiar a versão antiga do exemplo da documentação.

## Configuração da plataforma

No backend, configurar em ambiente protegido:

- `WHATSAPP_APP_ID`: App ID da plataforma.
- `WHATSAPP_APP_SECRET`: segredo do mesmo aplicativo, somente servidor.
- `WHATSAPP_EMBEDDED_CONFIG_ID`: ID da configuração de Facebook Login para Empresas destinada ao Cadastro Incorporado do WhatsApp.
- `WHATSAPP_CREDENTIAL_KEY`: chave AES-256 já usada pela configuração manual.
- Para recebimento, também configurar `WHATSAPP_VERIFY_TOKEN` e `WHATSAPP_PUBLIC_WEBHOOK_URL`.

No painel Meta: preparar aplicativo/negócio como provedor conforme requisitos aplicáveis, criar configuração de Login para Empresas com acesso adequado a WhatsApp Business, cadastrar os domínios usados pelo SDK e as URLs exigidas no painel, obter revisão/acesso avançado e colocar em modo de operação quando aprovado. Em desenvolvimento, as contas e os ativos precisam estar autorizados para o aplicativo. Validar os requisitos atuais no painel/documentação Meta. O frontend não usa App Secret nem token; App ID e Config ID são públicos e vêm da API autenticada. Não criar chaves fictícias em produção.

Sem a configuração completa, o botão aparece indisponível com explicação e a alternativa manual continua acessível. Configurar App ID/Config ID não substitui revisão/permissões Meta. A validação com conta real permanece pendente.

## Fluxo e proteção

1. Administrador abre o painel oficial. Consulta autenticada retorna apenas parâmetros públicos e disponibilidade.
2. O SDK carrega do domínio fixo connect.facebook.net; o backend prepara uma autorização válida por cinco minutos, vinculada à empresa, usuário, sessão autenticada e versão da conexão. O banco guarda só o hash do identificador de autorização.
3. Clique direto abre `FB.login` para evitar bloqueio de pop-up. Eventos são aceitos somente de origens HTTPS exatas da Meta; o payload do evento nunca concede acesso por si só.
4. Código e IDs selecionados ficam em memória e são enviados por POST BFF/API com proteção de origem. Código, segredo e estado nunca vão a URL da aplicação, localStorage, logs ou auditoria. A chamada servidor-Meta usa os parâmetros documentados e logs HTTP de terceiros permanecem desabilitados.
5. A autorização é consumida atomicamente antes da troca externa; fingerprint único do código impede reuso local, inclusive por outra empresa. Tentativa falha exige nova autorização. Expiração, sessão diferente e versão obsoleta são recusadas.
6. Reutiliza validação de vínculo número/WABA, inspeção de token/aplicativo/permissões, AES-GCM com contexto do tenant e atualização com controle de versão. O token nunca é devolvido ao navegador.
7. Diagnóstico do número e inscrição de eventos continuam visíveis. Registro/inscrição exigem as confirmações já existentes. Autorização concluída não significa recebimento/envio operacional; envio ainda depende de implementação/validação específica.

Cancelamento, timeout, SDK indisponível e recusa da Meta não geram conexão fictícia. O estado pendente é descartado no navegador; no servidor expira automaticamente. Tentativas antigas são removidas ao preparar novos fluxos após um dia de retenção além da validade. Tokens não são revogados automaticamente na Meta ao fechar uma janela; remoção local mantém o comportamento existente.

## Validação local

Pytest cobre troca de código, criptografia, ausência de segredos, permissões, sessão/tenant, expiração, replay, versão obsoleta e falhas do provedor. Vitest cobre origens falsas, ordem dos eventos, cancelamento e expiração. E2E usa Next/BFF/FastAPI e SQLite temporário reais, com apenas SDK/HTTP da Meta simulados. Não comprova onboarding real de uma conta Meta.
