# CHECKLIST — Backend AtendeHub

## Fase 01 essencial
- [x] FastAPI, SQLAlchemy 2 e SQLite de desenvolvimento.
- [x] Migrations Alembic e reversão/upgrade validados.
- [x] Cadastro atômico de empresa e administrador com trial de 7 dias.
- [x] Argon2, sessões HttpOnly, login, logout e revogação.
- [x] Isolamento multiempresa e permissões de administrador.
- [x] Bloqueio de trial vencido nas rotas operacionais.
- [x] Origem validada, rate limiting persistido e auditoria.
- [x] 20 testes Pytest validados no repositório independente.
- [x] Documentação de instalação, API e arquitetura.

## Próximas etapas (não implementadas)
- [ ] Recuperação segura de senha: depende de provedor de e-mail.
- [ ] Gestão completa de usuários, convites e superadmin da plataforma.
- [ ] PostgreSQL, TLS, proxy confiável, limites na borda, monitoramento e backups.
- [ ] Hospedagem da API com banco persistente.
- [ ] Módulos de atendimentos, WhatsApp, IA, ERP, clientes, produtos, orçamentos, conhecimento, dashboard real e relatórios.

Nenhum Docker executado. SQLite é exclusivo de desenvolvimento/testes. Não há credenciais externas ou usuários reais neste repositório.

## Edição de usuários
- [x] Editar usuários com isolamento por empresa e permissões, formulário em modal (padrão), tela cheia ou painel direito; validar e gerar prints.

Validação: 72 testes Vitest, 22 Pytest, build e lint aprovados. E2E validou salvamento real, persistência, contagem, troca de formatos sem perda de dados, dimensões desktop/mobile e preferência no navegador. Prints dos três modos gerados. Nenhum Docker executado.
