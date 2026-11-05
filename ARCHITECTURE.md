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
