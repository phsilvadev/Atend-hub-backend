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

A interface mantém o funil e o painel lateral, usa estados de carregamento/erro/vazio, consulta o backend e não inicializa conversas fictícias. O protótipo visual anterior está arquivado em `components/atendimentos/demo`, sem importação nas rotas. O proxy Next encaminha query strings validadas pela API para busca/paginação. IA, WhatsApp, leitura/não lidas, automação de horário, realtime e SLA continuam pendentes. O canal manual registra textos somente na central; não possui transporte externo.
