# CHECKLIST MESTRE — ATENDEHUB

Atualizado em 05/11/2026. Referência completa: [PROMPT_MESTRE.md](docs/PROMPT_MESTRE.md).

Este arquivo acompanha a plataforma completa; uma tela demonstrativa não comprova um módulo de backend. `[x]` significa implementado e validado no escopo descrito; `[ ]` significa pendente; `[ ] 🔄` significa em andamento. Nenhuma fase está concluída enquanto houver itens pendentes. O detalhamento de entregas anteriores permanece em [Histórico](docs/DEVELOPMENT_HISTORY.md).

## Decisões e escopo autorizado

- Marca SaaS AtendeHub; Aço Moreira é a primeira distribuidora prevista, não um tenant fixo no código.
- Frontend Next.js/TypeScript e API FastAPI em repositórios separados, ambos na branch development.
- SQLite em desenvolvimento/testes. PostgreSQL e pgvector permanecem pendentes para produção.
- Não executar Docker por instrução do usuário. Infraestrutura Docker fica adiada, sem marcar como pronta.
- Recuperação de senha foi explicitamente deixada para o final.
- Prioridade atual: fundação, equipe, configurações de empresa e planos. Próximas fases comerciais continuam no planejamento; não implementar todas de uma vez.
- Catálogo de planos fictício autorizado somente em desenvolvimento/testes, inserido por seed no banco e consumido por API. Cobrança real não foi autorizada/implementada nesta etapa.

## Correspondência com os 14 módulos do prompt

| Módulo | Fase de implementação |
|---|---|
| 01 Autenticação e usuários | 01 |
| 02 Empresas | 01 e 11 |
| 03 Central de atendimentos | 02 |
| 04 WhatsApp | 03 |
| 05 Inteligência artificial | 04 |
| 06 GestãoClick | 05 |
| 07 Clientes / 08 Produtos | 06 |
| 09 Orçamentos | 07 |
| 10 Base de conhecimento | 08 |
| 11 Dashboard | 09 |
| 12 Relatórios | 10 |
| 13 Configurações da IA | 11 |
| 14 Segurança e auditoria | 01 e 12, aplicada também em cada módulo |
| Extensão SaaS solicitada: planos | 13 |

## FASE 01 — FUNDAÇÃO, AUTENTICAÇÃO E MULTIEMPRESA

- [x] Inspecionar tecnologias, padrões e funcionalidades existentes; preservar frontend e contratos.
- [x] Definir separação entre API, schemas, serviços, repositórios e persistência.
- [x] Configurar Python/FastAPI, SQLAlchemy 2, Pydantic e Alembic.
- [x] Configurar SQLite de desenvolvimento/testes e migrations incrementais.
- [ ] Configurar PostgreSQL e validar migração de banco — adiado para preparação de produção.
- [ ] Configurar Docker/Compose — adiado por instrução expressa; nenhum Docker executado.
- [x] Cadastrar empresa e administrador atomicamente com trial de sete dias.
- [x] Autenticar com Argon2, sessões em cookie HttpOnly e opção lembrar acesso.
- [x] Implementar logout, expiração e revogação de sessões.
- [x] Definir papéis admin, supervisor, seller e operator; restringir ações administrativas.
- [x] Isolar usuários, sessões e perfil da empresa pelo tenant autenticado.
- [x] Proteger rotas no Next e conferir vínculo da empresa na API; recusar tenant arbitrário.
- [x] Bloquear operações de empresa/usuário inativo e trial vencido.
- [x] Listar, criar e editar usuários reais; ativar/desativar acessos.
- [x] Revogar sessões após mudanças de e-mail, perfil ou ativação; impedir autodesativação/rebaixamento.
- [x] Interface Equipe com contador, confirmação em modal e editor modal/tela cheia/painel direito.
- [x] Validar origem contra CSRF, entradas, erros sem senha e rate limiting persistido na autenticação.
- [x] Auditar cadastro, login/logout e alterações administrativas já implementadas.
- [x] Criar e executar testes de autenticação, permissões e isolamento com API real e SQLite temporário.
- [ ] Implementar superadministrador de plataforma sem expor cadastro público privilegiado.
- [ ] Implementar múltiplos vínculos de empresa por usuário e seleção de empresa, se adotado.
- [ ] Recuperação segura de senha com token temporário, envio de e-mail e revogação — deixada para o final.
- [ ] Convites por e-mail e verificação de endereço de e-mail.

## FASE 02 — CENTRAL DE ATENDIMENTOS

Núcleo local da central concluído e validado: cliente mínimo, conversa, responsável, status, histórico, leitura individual, contadores, atualização automática e tempos manuais. A validação integrada da Fase 02 continua aberta nos itens explicitamente dependentes de WhatsApp/IA (Fases 03/04). Não há execução de IA ou transporte externo nesta entrega.

- [x] Criar entidades de conversas e mensagens com company_id e índices.
- [x] Associar conversa ao cliente e registrar origem/canal.
- [ ] Implementar criação automática de atendimento a partir de mensagem recebida.
- [x] Criar endpoints de listagem, detalhe e filtros da central.
- [x] Implementar estados manuais: novo, humano, aguardando cliente, orçamento, convertido e encerrado.
- [ ] Ativar estado/execução de atendimento por IA e transições automáticas (enum reservado, uso bloqueado nesta etapa).
- [x] Atribuir vendedores e registrar histórico de atribuições.
- [ ] Transferir atendimento IA/humano com exclusão de respostas concorrentes.
- [x] Armazenar histórico manual: relato registrado, mensagem manual, nota interna e eventos de sistema, com ator/data e paginação.
- [ ] Receber/enviar mensagens externas e registrar identificadores/status reais de entrega via WhatsApp.
- [x] Registrar textos manuais com autorização por empresa e propriedade do atendimento. O registro não faz entrega externa.
- [ ] Enviar respostas ao cliente por transporte externo validado (Fase 03).
- [x] Controlar registros não lidos por usuário com cursor persistido, monotônico e autorizado por atendimento.
- [x] Exibir contadores reais e filtro Não lidos com escopo de empresa/propriedade.
- [x] Sincronizar lista/histórico a cada 5 segundos com aba visível, sem sobrepor ciclos ou perder rascunho/histórico paginado.
- [x] Persistir criação, última atualização e encerramento/reabertura dos atendimentos manuais.
- [x] Calcular primeira resposta manual e tempo acumulado de atendimento, pausando closed/converted e retomando ao reabrir.
- [ ] Aplicar horário comercial na execução automática (depende dos motores WhatsApp/IA, Fases 03/04/11).
- [x] Encerrar/reabrir atendimento e registrar auditoria.
- [x] Deduplicar criação/mensagens por chave de requisição e proteger atualizações por versão (compare-and-swap).
- [ ] Prevenir duplicidade de eventos externos e conflitos entre IA e vendedor após integrações.
- [x] Conectar frontend da central aos endpoints reais.
- [x] Testar transições manuais, atribuição humana, encerramento/reabertura, retry, versão obsoleta, permissões, isolamento e FKs compostas no banco.
- [ ] Testar transferência IA/humano e concorrência com workers/webhooks quando disponíveis.

## FASE 03 — WHATSAPP BUSINESS CLOUD API

- [ ] Validar documentação oficial e preparar credenciais por empresa — depende de conta Meta.
- [ ] Armazenar credenciais criptografadas ou em gerenciador de segredos.
- [ ] Implementar validação inicial e autenticação/assinatura dos webhooks.
- [ ] Receber eventos e mensagens de texto pela API oficial.
- [ ] Registrar IDs externos únicos e deduplicar webhooks.
- [ ] Enviar texto e registrar entrega, leitura e falhas.
- [ ] Respeitar janela de atendimento e templates aprovados.
- [ ] Configurar Redis e fila de processamento assíncrono adequada.
- [ ] Implementar retries com backoff, reprocessamento e tratamento de falhas.
- [ ] Preparar extensões para documentos, imagens e áudios.
- [ ] Conectar recebimento/envio à central de atendimentos.
- [ ] Testar assinatura, duplicidade, ordenação, retries e falhas externas.

## FASE 04 — MOTOR DE INTELIGÊNCIA ARTIFICIAL

- [ ] Configurar OpenAI API e tratamento seguro de chaves — depende de credenciais.
- [ ] Criar serviço de IA com histórico e contexto isolados por empresa.
- [ ] Criar prompts comerciais, tom e regras de segurança.
- [ ] Classificar intenções e identificar oportunidades comerciais.
- [ ] Extrair produtos, medidas, espessuras, quantidades e unidades.
- [ ] Reconhecer termos informais e solicitar dados ausentes/ambíguos.
- [ ] Consultar somente conhecimento técnico aprovado e dados comerciais oficiais.
- [ ] Implementar search_products e get_product_details.
- [ ] Implementar check_stock e get_product_price com origem e atualidade dos dados.
- [ ] Implementar get_customer e get_customer_purchase_history.
- [ ] Implementar calculate_material_weight com fórmulas e unidades verificadas.
- [ ] Implementar create_quote_draft e request_quote_approval.
- [ ] Implementar transfer_to_human e get_conversation_history.
- [ ] Validar entradas, permissões e tenant em cada ferramenta; exigir aprovação para alterações comerciais.
- [ ] Impedir invenção de preços, estoque, normas e características.
- [ ] Impedir dimensionamento estrutural definitivo e orientar responsável técnico quando necessário.
- [ ] Tratar mensagens/documentos como dados não confiáveis e testar prompt injection.
- [ ] Testar ferramentas, extração, recusas, segurança e transferência humana.

## FASE 05 — INTEGRAÇÃO GESTÃOCLICK ERP

- [ ] Consultar documentação oficial e confirmar endpoints e autenticação — bloqueio prévio a chamadas reais.
- [ ] Criar interface ERP e adaptador independente do fornecedor.
- [ ] Configurar credenciais seguras e permissões por empresa.
- [ ] Sincronizar produtos com IDs externos e controle incremental.
- [ ] Sincronizar clientes sem duplicidade.
- [ ] Consultar preços e estoque; ERP como fonte oficial.
- [ ] Consultar histórico de vendas e compras do cliente.
- [ ] Consultar orçamentos e status de pedidos.
- [ ] Criar orçamentos somente se suportado e validado pela API oficial.
- [ ] Registrar atualização, falhas e tentativas de sincronização.
- [ ] Testar autenticação, permissões, timeout, indisponibilidade, contratos e isolamento.

## FASE 06 — CATÁLOGO DE PRODUTOS E CLIENTES

- [ ] Criar produtos com company_id, ID ERP, SKU, nome, categoria e descrição.
- [ ] Cadastrar material, formato, espessura, largura, altura e comprimento.
- [ ] Cadastrar unidade comercial, peso teórico e disponibilidade.
- [ ] Pesquisar nome, código, categoria, medidas, descrição e sinônimos.
- [ ] Resolver termos como metalon 30 por 30 chapa 18 e solicitar confirmação de ambiguidades.
- [ ] Criar clientes por empresa, identificados por telefone normalizado e ID ERP.
- [ ] Evitar duplicidade de clientes e produtos em importações/sincronizações.
- [ ] Registrar vendedor responsável, classificação e observações internas.
- [ ] Consultar históricos de atendimento, orçamento e compras.
- [ ] Registrar produtos de interesse e última interação.
- [ ] Integrar telas de produtos/clientes aos endpoints reais.
- [ ] Testar cadastro, busca, duplicidade, histórico, proteção de dados e isolamento.

## FASE 07 — ORÇAMENTOS E OPORTUNIDADES

- [ ] Criar entidades de orçamento e itens por empresa e atendimento.
- [ ] Criar rascunhos e incluir produtos/quantidades.
- [ ] Consultar preços no ERP e registrar origem e horário da consulta.
- [ ] Calcular subtotal, descontos autorizados, frete e total com precisão decimal.
- [ ] Persistir condições comerciais e validade.
- [ ] Implementar status: rascunho, aprovação, enviado, negociação, aprovado, recusado, expirado e venda.
- [ ] Criar fluxo de aprovação por vendedor e histórico de alterações.
- [ ] Enviar proposta ao cliente após autorização.
- [ ] Integrar orçamento ao ERP conforme capacidades documentadas.
- [ ] Associar vendas confirmadas sem emissão fiscal/fechamento automático não autorizado.
- [ ] Registrar oportunidades e motivos de perda.
- [ ] Testar cálculos, desconto, autorização, expiração, integração e isolamento.

## FASE 08 — BASE DE CONHECIMENTO

- [ ] Criar documentos técnicos, categorias, versões e identificação de empresa.
- [ ] Importar catálogos e documentos com validação de arquivos.
- [ ] Cadastrar perguntas frequentes, políticas comerciais e respostas aprovadas.
- [ ] Cadastrar sinônimos e termos técnicos.
- [ ] Preparar conteúdo revisado: metalon, tubos industriais/galvanizados, vergalhões, chapas, cantoneiras e perfis U/I/H.
- [ ] Preparar conteúdo revisado: vigas, telhas, barras chatas/redondas e aços carbono/galvanizado/inoxidável.
- [ ] Validar conteúdo de bitolas, pesos teóricos, comprimentos, conversões e aplicações.
- [ ] Implementar aprovação humana, ativação/desativação e versionamento.
- [ ] Configurar pgvector, embeddings e busca semântica com isolamento por empresa.
- [ ] Registrar fontes e documentos utilizados nas respostas.
- [ ] Importar histórico WhatsApp somente de fontes autorizadas.
- [ ] Remover/proteger dados pessoais e extrair perguntas/termos recorrentes.
- [ ] Revisar conteúdo extraído antes de publicar; não confiar automaticamente no histórico.
- [ ] Testar recuperação, citações, permissões e conteúdo malicioso.

## FASE 09 — DASHBOARD COM DADOS REAIS

- [ ] Criar indicadores reais de atendimentos, orçamentos, vendas e novos clientes.
- [ ] Documentar cálculo e comparação das variações percentuais.
- [ ] Agregar atendimentos por status.
- [ ] Calcular conversão e evolução diária dos atendimentos/orçamentos.
- [ ] Listar últimos atendimentos e produtos mais consultados.
- [ ] Implementar filtros hoje, ontem, 7/30 dias, mês e período personalizado com fuso definido.
- [ ] Criar GET /api/v1/dashboard/overview consolidado.
- [ ] Substituir dados demonstrativos do dashboard por consumo real de API.
- [ ] Testar filtros, métricas, períodos sem dados, comparações e isolamento.

## FASE 10 — RELATÓRIOS COMERCIAIS

- [ ] Medir volume, primeira resposta e tempo médio de atendimento.
- [ ] Agregar atendimentos por vendedor.
- [ ] Medir resoluções por IA e transferências para humanos.
- [ ] Medir orçamentos, conversão e vendas associadas.
- [ ] Listar produtos procurados e solicitações sem correspondência.
- [ ] Apurar motivos de perda de oportunidades.
- [ ] Filtrar período, vendedor e empresa.
- [ ] Criar endpoints e interface de relatórios reais.
- [ ] Testar cálculos, filtros, permissões e isolamento.

## FASE 11 — CONFIGURAÇÕES POR EMPRESA

- [x] Persistir nome fantasia, razão social, CNPJ, telefone e e-mail comercial.
- [x] Persistir endereço estruturado, CEP e UF.
- [x] Persistir horários semanais e fuso IANA; validar abertura/encerramento.
- [x] Criar aba Empresa com consulta, edição administrativa, descarte e confirmação.
- [x] Validar CNPJ, contato, endereço, horários, permissões, isolamento e migration.
- [ ] Configurar assistente: nome, mensagem inicial e tom de comunicação.
- [ ] Configurar ativação da IA e instruções comerciais por empresa.
- [ ] Aplicar horários nas respostas automáticas e respostas fora de expediente.
- [ ] Configurar regras de transferência para humanos.
- [ ] Configurar limites de negociação, preços e aprovação de orçamento.
- [ ] Gerenciar integrações e credenciais criptografadas.
- [ ] Criar consulta administrativa de logs de auditoria.
- [ ] Testar configurações comerciais/IA e aplicação efetiva das regras.

## FASE 12 — SEGURANÇA, VALIDAÇÃO E PRODUÇÃO

- [x] Executar testes unitários e integrados dos módulos essenciais já entregues.
- [x] Testar autenticação, autorização e isolamento das rotas implementadas.
- [x] Recusar corpo com tenant/plano forjado nas operações administrativas existentes.
- [x] Evitar exposição de senha/hashes nas respostas e aplicar headers no-store/nosniff.
- [ ] Criptografar segredos de integrações e planejar rotação de chaves.
- [ ] Implementar validação de webhooks e idempotência de eventos comerciais.
- [ ] Ampliar logs estruturados, correlação de requisições e auditoria comercial.
- [ ] Definir política LGPD: retenção, minimização, exportação/exclusão e controle de acesso.
- [ ] Testar fluxo completo WhatsApp → IA → ERP.
- [ ] Testar transferência humana e orçamento ponta a ponta.
- [ ] Testar falhas externas e recuperação de filas.
- [ ] Revisar segurança de todos os módulos finais e testes de operações sensíveis.
- [ ] Configurar monitoramento, alertas, métricas e rastreamento de erros.
- [ ] Configurar backups e validar restauração em ambiente separado.
- [ ] Configurar implantação Next/FastAPI, PostgreSQL persistente, HTTPS e proxy confiável.
- [ ] Revisar rate limiting na borda e política de IP atrás do proxy.
- [ ] Configurar CI para checks e testes de ambos os repositórios.
- [ ] Validar documentação completa para produção e plano de operação.

## FASE 13 — PLANOS E ASSINATURA (EXTENSÃO SaaS)

- [x] Exibir plano real, status, datas de trial e usuários da empresa autenticada.
- [x] Criar catálogo de planos persistido no banco e migration aditiva.
- [x] Criar seed fictício idempotente, exclusivo de desenvolvimento/testes.
- [x] Consumir nomes, preços, limites e recursos pela API; sem catálogo hardcoded no front.
- [x] Adicionar skeleton de carregamento, erro/retry, catálogo vazio e estado de plano atual.
- [x] Testar catálogo, alteração de valores no banco, isolamento, trial e permissões; gerar prints.
- [ ] Habilitar definição comercial real de preços, limites e recursos após aprovação.
- [ ] Integrar checkout, provedor de pagamentos e webhooks de cobrança autenticados.
- [ ] Persistir assinatura, renovação, cancelamento, inadimplência e histórico financeiro.
- [ ] Aplicar limites/entitlements reais por plano e testar upgrades/downgrades.
- [ ] Disponibilizar fluxo de contratação após trial vencido sem liberar rotas operacionais.

## Dependências, bloqueios e próxima atividade

- Planos entregues no recorte de exibição, catálogo seed e skeleton. Cobrança/contratação e limites reais permanecem pendentes.
- Núcleo da Fase 02 entregue: conversas manuais, leitura, contadores, sincronização e tempos. Próximo: Fase 03, validar conta/documentação Meta e integrar webhook oficial. Execução/transferência de IA e validação ponta a ponta dependem das fases correspondentes.
- WhatsApp: conta Meta, número habilitado, app/webhook e credenciais oficiais.
- OpenAI: credenciais, escolha do modelo e definição de custeio por empresa/plataforma.
- GestãoClick: documentação oficial confirmada, acesso de integração e permissões; não há endpoints inventados.
- Conhecimento técnico: documentos confiáveis e revisão/aprovação humana.
- Produção: PostgreSQL, hospedagem persistente, TLS, observabilidade e restauração de backup; ainda não validada.
- E-mail: escolher provedor; recuperação de senha fica no final por decisão do usuário.
- Pagamentos: escolher provedor e definir regras comerciais reais; seed não constitui assinatura nem aplica limites.

## Evidências e regra de atualização

As entregas de fundação, equipe e empresa já possuem testes Pytest/Vitest e E2E reais com SQLite temporário. Validação da entrega de Planos: 79 testes Vitest, 38 Pytest e 8 cenários E2E aprovados, além de build/lint. Testes cobrem seed idempotente, alteração de preço/nome no banco, exclusão de planos inativos/demo em produção, trial ativo/expirado, plano atual, isolamento, skeleton e layout mobile. Reexecução de Planos após ajustes finais aprovada; formatação de centavos testada. Seed aplicado no SQLite local de desenvolvimento; nenhuma cobrança nem Docker executado. Prints desktop/mobile e skeleton gerados. Build/lint e os testes pertinentes devem passar antes de marcar uma nova tarefa.

Leia este arquivo antes de cada tarefa; selecione item/dependências; sinalize em andamento; implemente; valide; atualize README/API/arquitetura quando aplicável; registre resultado e bloqueios. Não interpretar módulos pendentes como autorização para implementá-los todos de uma vez.

### Execução atual — Fase 02 manual
- [x] Criar migration, entidades e API de conversas/mensagens com autorização e controle de concorrência.
- [x] Conectar a central existente à API com criação, atribuição, status e histórico manual.
- [x] Testar persistência, permissões, isolamento, duplicidade de requisições e conflitos; gerar prints.

Validação da Fase 02 manual: 86 testes Vitest, 44 Pytest e 9 E2E aprovados, além de build e lint. Inclui API real/SQLite temporário, reload, busca, atribuição, histórico, encerramento/reabertura, versão obsoleta, retries, isolamento e restrição de propriedade; FKs no banco também rejeitam vínculos cruzados. Busca por telefone formatado revalidada; captura mobile aguarda fim da animação e confere dimensões. Migration aplicada ao SQLite local, sem inserir conversas fictícias. Protótipo anterior preservado em pasta demo sem importação pelas rotas. Nenhum Docker executado.

### Execução atual — conclusão da central antes das integrações
- [x] Persistir leitura individual e contagens de registros não lidos com isolamento/autorização.
- [x] Atualizar lista e histórico automaticamente sem perder rascunhos ou paginação.
- [x] Registrar primeira resposta manual e tempo de atendimento, respeitando fechamento/reabertura.
- [x] Testar concorrência real, marcações de leitura fora de ordem, troca de responsável e acesso revogado.
- [x] Atualizar documentação/checklist e capturar prints desktop/mobile.

Validação da conclusão do núcleo local: 88 testes Vitest, 49 testes Pytest e 10 E2E aprovados, com build/lint. Inclui disputa de atribuição e mensagens/leituras concorrentes por threads reais, cursor monotônico, duas sessões no navegador, rascunho durante atualização e limpeza do painel após transferência. Migration downgrade/upgrade preservou mensagens e preencheu métricas; aplicada no SQLite local. Prints de contadores e histórico desktop/mobile gerados com dados de teste. Fase 02 não é marcada integralmente concluída enquanto as dependências externas listadas permanecerem abertas. Nenhum Docker executado.
