# Acesso do cliente: Google e recuperação de senha

Implementação em 09/11/2026. O login do superadmin continua separado, sem Google. Cadastro por e-mail/senha mantém o teste de sete dias e os contratos existentes.

## Google Identity Services

Fontes oficiais consultadas:
- https://developers.google.com/identity/gsi/web/guides/verify-google-id-token
- https://developers.google.com/identity/gsi/web/reference/js-reference

Criar credencial OAuth de aplicativo Web no Google Cloud e cadastrar as origens JavaScript exatas do frontend (desenvolvimento e produção) e a tela de consentimento conforme regras do Google. Configurar `GOOGLE_AUTH_CLIENT_ID` no backend. Neste fluxo, o SDK retorna um ID token assinado: não utiliza OAuth Client Secret, nem guarda access/refresh token Google. O Client ID é público; o token de identidade é temporário e enviado somente ao backend pelo BFF.

`/auth/google/start` gera state, nonce e cookie HttpOnly de fluxo, válidos por cinco minutos. O banco contém somente hashes e o modo login/cadastro. SDK oficial usa nonce e botão renderizado pelo provedor. `/complete` exige o cookie do navegador, consome a tentativa atomicamente e mantém Turnstile da modalidade correspondente. O backend usa google-auth para validar assinatura, expiração, issuer e audience; exige e-mail verificado e nonce correspondente. Apenas depois resolve o usuário e emite a sessão HttpOnly já usada no sistema.

Vínculo persistido pelo identificador `sub` do Google, nunca por um tenant enviado pelo navegador. Novo cadastro cria empresa/admin/trial em uma transação, com senha aleatória desconhecida (pode criar uma senha pessoal pelo fluxo de recuperação). Usuários desativados/empresas inativas não entram.

No primeiro login de uma conta existente por senha, vínculo por e-mail é permitido apenas quando o Google é autoridade pelo endereço: Gmail ou domínio Workspace confirmado no claim `hd`. Para endereço externo sem domínio confirmado, não há vinculação automática: informar acesso por e-mail/senha. Essa restrição evita assumir propriedade de e-mails externos apenas pelo claim email_verified. Cadastros novos não sobrescrevem conta existente. Reuso de state, cookie divergente ou nonce inválido não cria sessão. Não há elevação ao superadmin.

## Recuperação por e-mail

Configurar no backend, fora do Git:
- `AUTH_PUBLIC_ORIGIN`: origem exata do frontend, também presente em ALLOWED_ORIGINS. HTTPS em produção; HTTP só em localhost no desenvolvimento.
- `SMTP_HOST`, `SMTP_PORT` (587 por padrão), `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`.

Transporte usa STARTTLS com validação TLS obrigatória antes da autenticação. Não suporta SMTP implícito SSL/465 nesta entrega. Sem configuração, a opção mostra indisponibilidade e o endpoint retorna 503 antes de pesquisar contas.

Solicitação exige Turnstile com action `client_password_reset` e rate limiting por IP/e-mail. A resposta 202 é genérica para conta existente/inexistente/inativa. Envio é uma tarefa em processo após persistir o pedido; falha gera apenas aviso genérico no log, sem destinatário/token/credenciais. Não há fila durável nem retry automático de SMTP nesta entrega: em interrupção/falha, solicitar novo link.

Link contém `/redefinir-senha#token=...`: o fragmento não é enviado no GET ao servidor nem a referrers. A página move o token só para memória e limpa a URL. O banco guarda hash do token e fingerprint da versão da senha, com validade de quinze minutos. Novo pedido invalida os anteriores. Redefinição consome o pedido atomicamente, muda o hash Argon2, invalida todos os pedidos do usuário e revoga todas as suas sessões. Não autentica automaticamente nem altera senha de outra empresa. O login por senha usa comparação atômica e bloqueio da versão verificada para não criar sessão nova a partir de uma senha antiga durante uma redefinição concorrente. Links expirados, repetidos ou anteriores a troca de senha são recusados.

## Operação e validação

Publicar exige migration `20261109_client_auth` aplicada. Apenas desenvolvimento usa SQLite; PostgreSQL segue obrigatório em produção. As rotas públicas Next são login/cadastro/esqueci-senha/redefinir-senha; o restante mantém middleware e validação por tenant. Sem Google/SMTP configurados, a interface não simula sucesso.

Pytest usa assinatura RSA real para validar claims Google, além de testes de transação, nonce/cookie, replay, recuperação, expiração, concorrência e revogação. E2E usa Next/BFF/FastAPI e SQLite temporário reais; somente SDK/verificação Google e transporte SMTP são simulados. Login com conta Google real e entrega SMTP real dependem de configuração externa e permanecem pendentes. Nenhum segredo/token vai a localStorage, Git ou logs. Código publicado na API com autorização do usuário; configuração e validação de provedores reais continuam pendentes.
