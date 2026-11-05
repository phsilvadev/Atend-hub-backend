# PROMPT MESTRE — BACKEND AÇO MOREIRA IA ATENDIMENTO

## 1. OBJETIVO DO PROJETO

Você será o engenheiro de software responsável por desenvolver o backend completo de uma plataforma SaaS de atendimento comercial com inteligência artificial, especializada em distribuidoras de ferro e aço.

**Nome do sistema:** Aço Moreira IA Atendimento

O sistema deverá integrar:

- WhatsApp Business Cloud API.
- GestãoClick ERP.
- Inteligência artificial da OpenAI.
- Banco de dados PostgreSQL.
- Painel administrativo web.
- Central de atendimentos.
- Gestão de clientes.
- Gestão de produtos.
- Orçamentos e oportunidades comerciais.
- Base de conhecimento especializada em ferro e aço.
- Relatórios e indicadores comerciais.
- Gerenciamento de usuários e empresas.

Inicialmente, o sistema será utilizado pela Aço Moreira, mas a arquitetura deverá permitir que outras distribuidoras utilizem a plataforma futuramente.

O objetivo é transformar a IA em um vendedor técnico virtual, capaz de compreender solicitações comerciais, identificar produtos, consultar informações atualizadas, auxiliar na elaboração de orçamentos e encaminhar negociações para vendedores humanos.

---

## 2. INSTRUÇÕES OBRIGATÓRIAS PARA O CODEX

Antes de desenvolver qualquer funcionalidade:

1. Analise todo o repositório existente.
2. Identifique tecnologias e padrões já utilizados.
3. Verifique os arquivos, dependências e configurações.
4. Identifique funcionalidades já implementadas.
5. Não recrie funcionalidades existentes.
6. Não apague código funcional sem justificativa.
7. Preserve o frontend e os contratos existentes.
8. Elabore um plano de desenvolvimento por fases.
9. Crie o arquivo `CHECKLIST.md` na raiz do projeto.
10. Crie o arquivo `ARCHITECTURE.md` documentando a arquitetura.
11. Crie o arquivo `README.md` com a visão geral e as instruções de execução.

**REGRA PRINCIPAL:**

O desenvolvimento deverá ser incremental e organizado.

Não tente implementar todo o projeto em uma única etapa.

Implemente uma fase por vez, valide os resultados e atualize o checklist.

Não marque uma tarefa como concluída sem implementar e verificar sua funcionalidade.

---

## 3. ARQUITETURA TECNOLÓGICA

Se o repositório ainda não possuir uma arquitetura definida, utilize:

### Backend

- Python 3.12+
- FastAPI
- SQLAlchemy 2
- Pydantic
- Alembic
- PostgreSQL
- Redis
- Celery ou outro sistema adequado de filas
- Pytest

### Inteligência artificial

- OpenAI API
- Ferramentas de execução de funções
- Busca semântica com pgvector
- Base de conhecimento técnica
- Histórico de conversas
- Regras comerciais configuráveis

### Integrações

- WhatsApp Business Cloud API
- GestãoClick ERP API
- Webhooks
- Processamento assíncrono
- Sincronização de dados

### Infraestrutura

- Docker
- Docker Compose
- Variáveis de ambiente
- Logs estruturados
- Backups
- Monitoramento

A arquitetura deverá separar claramente API, regras de negócio, persistência, processamento assíncrono e integrações externas.

---

## 4. ESTRUTURA SUGERIDA DO PROJETO

```text
aco-moreira-ia/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── repositories/
│   │   ├── integrations/
│   │   │   ├── whatsapp/
│   │   │   ├── gestaoclick/
│   │   │   └── openai/
│   │   ├── ai/
│   │   │   ├── agents/
│   │   │   ├── tools/
│   │   │   ├── knowledge/
│   │   │   └── prompts/
│   │   ├── workers/
│   │   └── main.py
│   │
│   ├── migrations/
│   ├── tests/
│   └── requirements.txt
│
├── frontend/
├── docs/
├── docker-compose.yml
├── .env.example
├── README.md
├── ARCHITECTURE.md
└── CHECKLIST.md
```

Adapte a estrutura caso o projeto existente utilize convenções diferentes.

---

# 5. MÓDULOS DO BACKEND

## MÓDULO 01 — AUTENTICAÇÃO E USUÁRIOS

Implementar:

- Login e autenticação.
- Gerenciamento de sessões.
- Recuperação segura de senha.
- Controle de permissões.
- Cadastro de administradores.
- Cadastro de vendedores.
- Cadastro de supervisores.
- Ativação e desativação de usuários.
- Auditoria de operações importantes.

Perfis iniciais:

- Superadministrador da plataforma.
- Administrador da distribuidora.
- Supervisor comercial.
- Vendedor.
- Operador de atendimento.

Utilizar controle de acesso por perfil e empresa.

---

## MÓDULO 02 — GESTÃO DE EMPRESAS

Preparar a plataforma para múltiplas distribuidoras.

Cada empresa deverá possuir:

- Cadastro próprio.
- Usuários próprios.
- Clientes próprios.
- Produtos próprios.
- Configurações comerciais.
- Credenciais de integração.
- Base de conhecimento.
- Assistente de IA.
- Histórico de atendimentos.
- Relatórios.

Todas as tabelas operacionais deverão ter identificação da empresa.

Impedir acesso cruzado entre empresas.

As credenciais de integrações devem ser armazenadas de maneira segura, preferencialmente com criptografia ou gerenciador de segredos.

---

## MÓDULO 03 — CENTRAL DE ATENDIMENTOS

Desenvolver o backend da central de conversas.

Funcionalidades:

- Receber mensagens do WhatsApp.
- Armazenar histórico de conversas.
- Identificar clientes.
- Criar atendimentos automaticamente.
- Classificar status.
- Atribuir vendedores.
- Transferir atendimentos da IA para humanos.
- Permitir respostas manuais.
- Registrar mensagens enviadas e recebidas.
- Identificar mensagens não lidas.
- Registrar horários de atendimento.
- Registrar origem da conversa.
- Encerrar e reabrir atendimentos.

Status iniciais:

- Novo.
- Em atendimento pela IA.
- Em atendimento humano.
- Aguardando cliente.
- Em orçamento.
- Convertido em venda.
- Encerrado.

Implementar mecanismos para evitar mensagens duplicadas e conflitos entre IA e vendedor humano.

---

## MÓDULO 04 — INTEGRAÇÃO WHATSAPP

Implementar integração oficial com WhatsApp Business Cloud API.

Funcionalidades:

- Configuração das credenciais.
- Validação de webhooks.
- Recebimento de mensagens.
- Envio de mensagens.
- Registro de identificadores externos.
- Atualização do status de entrega.
- Tratamento de erros.
- Processamento assíncrono.
- Reconexão e tentativas de reprocessamento.
- Suporte a mensagens de texto e, futuramente, documentos, imagens e áudios.

Respeitar as regras da plataforma, inclusive janelas de atendimento e templates aprovados quando exigidos.

Não implementar automações baseadas em métodos não oficiais.

---

## MÓDULO 05 — INTELIGÊNCIA ARTIFICIAL

Criar o motor central de IA.

A inteligência deverá:

- Interpretar mensagens dos clientes.
- Identificar intenções comerciais.
- Extrair nomes de produtos.
- Identificar medidas, espessuras e quantidades.
- Reconhecer linguagem informal do setor.
- Consultar a base de conhecimento.
- Consultar ferramentas de integração.
- Solicitar informações ausentes.
- Responder perguntas técnicas.
- Ajudar na elaboração de orçamentos.
- Identificar oportunidades comerciais.
- Transferir conversas para vendedores quando necessário.

### Conhecimento especializado

Preparar conteúdo sobre:

- Metalon.
- Tubos industriais.
- Tubos galvanizados.
- Vergalhões.
- Chapas de aço.
- Cantoneiras.
- Perfis U, I e H.
- Vigas.
- Telhas metálicas.
- Barras chatas.
- Barras redondas.
- Aço carbono.
- Aço galvanizado.
- Aço inoxidável.
- Espessuras e bitolas.
- Pesos teóricos.
- Comprimentos comerciais.
- Conversões de unidades.
- Aplicações dos materiais.

A IA deverá utilizar documentos técnicos confiáveis e informações comerciais aprovadas pela empresa.

Não poderá inventar preços, estoque, normas técnicas ou características de produtos.

Não deverá fornecer dimensionamento estrutural definitivo ou substituir um engenheiro responsável.

### Ferramentas da IA

Preparar funções controladas:

- `search_products`
- `get_product_details`
- `check_stock`
- `get_customer`
- `get_customer_purchase_history`
- `get_product_price`
- `calculate_material_weight`
- `create_quote_draft`
- `request_quote_approval`
- `transfer_to_human`
- `get_conversation_history`

Cada ferramenta deverá validar permissões, entradas e contexto da empresa.

Operações que alterem dados comerciais deverão exigir autorização conforme as regras configuradas.

---

## MÓDULO 06 — INTEGRAÇÃO GESTÃOCLICK ERP

Criar uma camada independente de integração.

Funcionalidades previstas:

- Sincronização de produtos.
- Sincronização de clientes.
- Consulta de preços.
- Consulta de estoque.
- Consulta de histórico de vendas.
- Consulta de orçamentos.
- Criação de orçamentos, quando suportada.
- Consulta de status de pedidos.
- Atualização de informações comerciais.

**Importante:** antes de implementar chamadas reais, consultar a documentação oficial do GestãoClick e confirmar os endpoints, permissões e métodos de autenticação disponíveis.

Não inventar endpoints.

Criar adaptadores e interfaces para permitir que futuramente sejam integrados outros ERPs.

O ERP deverá ser a fonte oficial de preços, estoque e registros comerciais.

---

## MÓDULO 07 — CLIENTES

Implementar:

- Cadastro de clientes.
- Identificação por telefone.
- Integração com o cadastro do ERP.
- Histórico de atendimentos.
- Histórico de orçamentos.
- Histórico de compras.
- Produtos de interesse.
- Vendedor responsável.
- Última interação.
- Classificação comercial.
- Observações internas.

Evitar duplicidade de clientes.

Respeitar permissões de acesso e regras de proteção de dados pessoais.

---

## MÓDULO 08 — PRODUTOS

Criar catálogo de produtos integrado ao ERP.

Campos principais:

- Identificador interno.
- Identificador do ERP.
- Código SKU.
- Nome.
- Categoria.
- Descrição.
- Material.
- Formato.
- Espessura.
- Largura.
- Altura.
- Comprimento.
- Unidade comercial.
- Peso teórico.
- Status de disponibilidade.

Criar mecanismos de pesquisa por:

- Nome.
- Código.
- Categoria.
- Medidas.
- Sinônimos.
- Descrição informal.

Exemplo:

O cliente poderá solicitar "metalon 30 por 30 chapa 18" e o sistema deverá localizar o produto correspondente no catálogo, solicitando confirmação quando houver ambiguidade.

---

## MÓDULO 09 — ORÇAMENTOS

Implementar:

- Criação de rascunhos.
- Inclusão de produtos.
- Quantidades.
- Preços consultados no ERP.
- Cálculo de subtotal.
- Descontos autorizados.
- Condições comerciais.
- Frete, quando disponível.
- Total.
- Validade.
- Status da proposta.
- Aprovação por vendedor.
- Envio ao cliente.
- Histórico de alterações.
- Associação ao atendimento.

Status:

- Rascunho.
- Aguardando aprovação.
- Enviado.
- Em negociação.
- Aprovado.
- Recusado.
- Expirado.
- Convertido em venda.

Registrar a origem e o horário dos preços utilizados.

Não confirmar vendas ou emitir documentos fiscais automaticamente sem autorização explícita e integração validada.

---

## MÓDULO 10 — BASE DE CONHECIMENTO

Criar um sistema de gerenciamento do conhecimento da IA.

Permitir:

- Cadastro de documentos técnicos.
- Importação de catálogos.
- Cadastro de perguntas frequentes.
- Cadastro de políticas comerciais.
- Cadastro de sinônimos de produtos.
- Cadastro de respostas aprovadas.
- Classificação de conteúdos.
- Versionamento.
- Ativação e desativação de documentos.
- Busca semântica.
- Identificação de documentos utilizados nas respostas.

### Histórico do WhatsApp

Preparar um processo para aproveitar conversas anteriores.

Etapas:

1. Importar conversas de fontes autorizadas.
2. Remover ou proteger dados pessoais desnecessários.
3. Identificar perguntas recorrentes.
4. Extrair termos comerciais e técnicos.
5. Organizar perguntas e respostas.
6. Submeter conhecimento extraído à revisão humana.
7. Publicar somente conteúdo aprovado.

Não considerar automaticamente toda resposta histórica como correta.

---

## MÓDULO 11 — DASHBOARD

Criar endpoints para alimentar o Dashboard já definido no frontend.

Indicadores:

- Total de atendimentos.
- Orçamentos gerados.
- Vendas convertidas.
- Novos clientes.
- Variação percentual dos indicadores.

Gráficos:

- Atendimentos por status.
- Taxa de conversão.
- Evolução dos atendimentos.
- Evolução dos orçamentos.

Listagens:

- Últimos atendimentos.
- Produtos mais consultados.

Filtros:

- Hoje.
- Ontem.
- Últimos 7 dias.
- Últimos 30 dias.
- Este mês.
- Período personalizado.

Criar endpoint consolidado:

`GET /api/v1/dashboard/overview`

Documentar as regras de cálculo e garantir que os dados sejam provenientes do banco de dados e das integrações, nunca de valores fictícios em produção.

---

## MÓDULO 12 — RELATÓRIOS COMERCIAIS

Implementar:

- Volume de atendimentos.
- Tempo médio de primeira resposta.
- Tempo médio de atendimento.
- Atendimentos por vendedor.
- Atendimentos resolvidos pela IA.
- Transferências para humanos.
- Quantidade de orçamentos.
- Taxa de conversão.
- Vendas associadas aos atendimentos.
- Produtos mais procurados.
- Produtos solicitados e não encontrados.
- Motivos de perda de oportunidades.

Preparar filtros por período, vendedor e empresa.

---

## MÓDULO 13 — CONFIGURAÇÕES DA IA

Permitir configurar por empresa:

- Nome do assistente.
- Mensagem inicial.
- Tom de comunicação.
- Horário de atendimento.
- Regras de transferência.
- Limites de negociação.
- Regras para consulta de preços.
- Regras de aprovação de orçamento.
- Respostas fora do horário.
- Instruções comerciais.
- Status de ativação da IA.

As configurações deverão ser persistidas no banco de dados.

---

## MÓDULO 14 — SEGURANÇA E AUDITORIA

Implementar:

- Autenticação segura.
- Autorização por função.
- Isolamento multiempresa.
- Criptografia de segredos.
- Validação de webhooks.
- Rate limiting.
- Logs estruturados.
- Auditoria de operações comerciais.
- Proteção contra duplicidade de eventos.
- Backups.
- Tratamento de erros.
- Política de retenção de dados.
- Recursos necessários ao atendimento da LGPD.

Mensagens recebidas e documentos externos devem ser tratados como dados não confiáveis, inclusive para prevenir instruções maliciosas direcionadas à IA.

---

# 6. CHECKLIST OBRIGATÓRIO

Crie o arquivo `CHECKLIST.md` na raiz do repositório.

Esse arquivo será o controle oficial de desenvolvimento.

Utilize caixas de seleção Markdown:

- `[ ]` Pendente.
- `[x]` Concluído e validado.

Para tarefas em andamento, mantenha `[ ]` e acrescente a indicação `🔄 Em andamento`.

### Estrutura inicial do CHECKLIST.md

```markdown
# CHECKLIST — AÇO MOREIRA IA

## FASE 01 — FUNDAÇÃO
- [ ] Analisar repositório
- [ ] Definir arquitetura
- [ ] Configurar backend
- [ ] Configurar PostgreSQL
- [ ] Configurar migrations
- [ ] Configurar Docker
- [ ] Criar autenticação
- [ ] Criar permissões
- [ ] Criar estrutura multiempresa
- [ ] Criar testes iniciais

## FASE 02 — ATENDIMENTOS
- [ ] Criar entidades de conversas
- [ ] Criar entidades de mensagens
- [ ] Criar endpoints de atendimentos
- [ ] Criar controle de status
- [ ] Criar atribuição de vendedores
- [ ] Criar transferência IA/humano
- [ ] Criar histórico de mensagens

## FASE 03 — WHATSAPP
- [ ] Configurar integração oficial
- [ ] Criar webhook
- [ ] Validar autenticidade
- [ ] Receber mensagens
- [ ] Enviar mensagens
- [ ] Implementar idempotência
- [ ] Implementar processamento assíncrono
- [ ] Tratar erros e tentativas

## FASE 04 — INTELIGÊNCIA ARTIFICIAL
- [ ] Configurar OpenAI API
- [ ] Criar serviço de IA
- [ ] Criar instruções principais
- [ ] Criar classificação de intenções
- [ ] Criar extração de produtos
- [ ] Criar ferramentas de consulta
- [ ] Criar regras de segurança
- [ ] Criar transferência para vendedor
- [ ] Criar testes de atendimento

## FASE 05 — GESTÃOCLICK
- [ ] Validar documentação oficial
- [ ] Configurar autenticação
- [ ] Criar adaptador ERP
- [ ] Sincronizar produtos
- [ ] Sincronizar clientes
- [ ] Consultar preços
- [ ] Consultar estoque
- [ ] Consultar orçamentos
- [ ] Consultar vendas
- [ ] Testar sincronizações

## FASE 06 — PRODUTOS E CLIENTES
- [ ] Criar módulo de produtos
- [ ] Criar pesquisa de produtos
- [ ] Criar sinônimos técnicos
- [ ] Criar módulo de clientes
- [ ] Criar histórico comercial
- [ ] Criar prevenção de duplicidades

## FASE 07 — ORÇAMENTOS
- [ ] Criar entidades
- [ ] Criar itens de orçamento
- [ ] Criar cálculos
- [ ] Criar regras de desconto
- [ ] Criar fluxo de aprovação
- [ ] Integrar ao ERP
- [ ] Criar acompanhamento de status

## FASE 08 — BASE DE CONHECIMENTO
- [ ] Criar estrutura de documentos
- [ ] Criar importação
- [ ] Criar busca semântica
- [ ] Criar sinônimos
- [ ] Criar perguntas frequentes
- [ ] Criar revisão humana
- [ ] Criar versionamento
- [ ] Criar testes de recuperação

## FASE 09 — DASHBOARD
- [ ] Criar indicadores
- [ ] Criar gráfico de status
- [ ] Criar gráfico de conversão
- [ ] Criar últimos atendimentos
- [ ] Criar produtos mais consultados
- [ ] Criar filtros
- [ ] Criar endpoint consolidado

## FASE 10 — RELATÓRIOS
- [ ] Criar métricas de atendimento
- [ ] Criar métricas da IA
- [ ] Criar métricas comerciais
- [ ] Criar relatórios por vendedor
- [ ] Criar filtros de período

## FASE 11 — CONFIGURAÇÕES
- [ ] Criar configurações da empresa
- [ ] Criar configurações da IA
- [ ] Criar configurações comerciais
- [ ] Criar gerenciamento de integrações
- [ ] Criar logs de auditoria

## FASE 12 — VALIDAÇÃO E PRODUÇÃO
- [ ] Executar testes unitários
- [ ] Executar testes de integração
- [ ] Testar isolamento multiempresa
- [ ] Testar permissões
- [ ] Testar fluxo completo WhatsApp → IA → ERP
- [ ] Testar transferência humana
- [ ] Testar criação de orçamento
- [ ] Validar segurança
- [ ] Configurar monitoramento
- [ ] Configurar backups
- [ ] Preparar implantação
- [ ] Validar documentação
```

---

# 7. REGRAS PARA ATUALIZAR O CHECKLIST

O Codex deverá seguir estas regras durante todo o desenvolvimento:

1. Ler `CHECKLIST.md` antes de iniciar cada tarefa.
2. Identificar a próxima tarefa pendente e suas dependências.
3. Registrar a tarefa em andamento.
4. Implementar a funcionalidade.
5. Criar ou atualizar os testes.
6. Executar as validações disponíveis.
7. Marcar `[x]` somente após a conclusão e validação.
8. Registrar problemas ou bloqueios encontrados.
9. Atualizar o README quando houver alterações relevantes.
10. Informar o que foi concluído e qual será o próximo passo.

Se uma tarefa depender de credenciais externas, documentação ou aprovação, registrá-la como bloqueada, sem marcar como concluída.

Não marcar uma fase inteira como concluída se existirem tarefas pendentes.

---

# 8. TESTES OBRIGATÓRIOS

Criar testes automatizados para:

- Autenticação.
- Permissões.
- Isolamento entre empresas.
- Cadastro de clientes.
- Pesquisa de produtos.
- Processamento de mensagens.
- Duplicidade de webhooks.
- Ferramentas da IA.
- Consultas ao ERP.
- Cálculos de orçamento.
- Regras comerciais.
- Transferência de atendimento.
- Indicadores do Dashboard.
- Relatórios.
- Falhas de integração.
- Segurança de operações sensíveis.

Utilizar dados fictícios apenas em testes e ambientes demonstrativos.

---

# 9. DOCUMENTAÇÃO

Manter os seguintes arquivos atualizados:

**README.md**
- Visão geral.
- Tecnologias.
- Instalação.
- Configuração.
- Execução.
- Testes.

**ARCHITECTURE.md**
- Arquitetura.
- Módulos.
- Banco de dados.
- Integrações.
- Fluxos.
- Decisões técnicas.

**CHECKLIST.md**
- Fases.
- Tarefas.
- Status.
- Bloqueios.
- Próximas atividades.

**API.md**
- Endpoints.
- Métodos HTTP.
- Parâmetros.
- Autenticação.
- Exemplos de requisições.
- Exemplos de respostas.

---

# 10. INSTRUÇÃO FINAL PARA EXECUÇÃO

Você é responsável por construir um backend profissional, seguro, modular e escalável.

Sua prioridade inicial NÃO é implementar todas as funcionalidades.

Sua prioridade é:

1. Inspecionar o repositório.
2. Identificar o estado atual.
3. Definir a arquitetura.
4. Criar `README.md`, `ARCHITECTURE.md` e `CHECKLIST.md`.
5. Dividir tarefas grandes em subtarefas executáveis.
6. Identificar dependências e bloqueios.
7. Apresentar o planejamento.
8. Iniciar a Fase 01 após o planejamento, respeitando as convenções do repositório.

Durante a implementação:

- Não modificar desnecessariamente o frontend.
- Não inventar integrações externas.
- Não expor credenciais.
- Não utilizar dados fictícios em produção.
- Não ignorar testes.
- Não marcar tarefas incompletas como concluídas.
- Não implementar funcionalidades fora da fase atual sem necessidade técnica.

Ao terminar cada etapa, apresentar:

**RELATÓRIO DE DESENVOLVIMENTO**

- Fase atual:
- Tarefas concluídas:
- Arquivos criados:
- Arquivos modificados:
- Testes executados:
- Resultados:
- Pendências:
- Bloqueios:
- Próxima tarefa:

O objetivo final é entregar uma plataforma completa de atendimento comercial com inteligência artificial, especializada no setor de ferro e aço, integrada ao WhatsApp e ao GestãoClick ERP, preparada para operação real e expansão futura para múltiplas distribuidoras.