# Plataforma, empresas e conhecimento comum

## Divisão de responsabilidade adotada

| Cliente/distribuidora | Plataforma/superadministrador |
|---|---|
| Conectar seu próprio WhatsApp Business Cloud API. | Importar arquivos de conversas cuja utilização foi autorizada. |
| Receber/enviar mensagens nos seus atendimentos. | Organizar linguagem, perguntas, objeções e termos do setor. |
| Conectar seu GestãoClick para preços, estoque e registros oficiais. | Revisar documentos e publicar conhecimento genérico de ferro/aço. |
| Manter políticas de desconto, pagamento, entrega e frete particulares. | Administrar futuramente OpenAI, consumo, custos e planos. |

Não há conexão WhatsApp da plataforma para este fluxo de conhecimento. Não existe coleta automática dos atendimentos das empresas. Uma conta de plataforma não é uma conta de tenant e não ganha acesso às conversas operacionais pela autenticação de plataforma.

## O que está implementado nesta etapa

- Conta de plataforma separada, criada exclusivamente por comando no servidor; login/me/logout com sessão própria de uma hora, Argon2, revogação, validação de origem e limite de tentativas.
- Importação explícita de arquivo JSON normalizado (até 512 KiB, 200 turnos de até 3.000 caracteres), com referência de autorização e identificador de requisição para retries.
- Redação assistida de e-mails, telefones, CPF/CNPJ, links e termos identificadores fornecidos pelo operador. Mensagens que tratam de preços/condições particulares são substituídas por marcador de remoção comercial.
- O corpo original do arquivo e a lista de nomes/termos não são armazenados. A referência de autorização fica restrita à plataforma; não é fonte pública. São armazenados conteúdo tratado, hash para retry e metadados mínimos de operação.
- Extração determinística de pares adjacentes customer/agent (`adjacent_turns_v1`), gerando FAQs em rascunho. Não há chamada OpenAI, fine-tuning nem garantia automática de que a resposta histórica esteja correta.
- Cadastro manual de FAQ, texto técnico, sinônimo ou resposta aprovada; categoria e fonte obrigatórias. Edição cria revisão imutável e usa versão para detectar concorrência.
- Publicação exige revisão humana explícita de privacidade, direito de uso e ausência de condições comerciais particulares. Formatos conhecidos de contato/preços ainda presentes bloqueiam a publicação. As confirmações não substituem a conferência humana da validade técnica e do direito de uso.
- Clientes consultam apenas versões publicadas e ativas da biblioteca comum. Uma nova revisão em rascunho não substitui a versão anterior aprovada. Desativação impede novas consultas imediatamente.
- Auditoria separada para operações da plataforma, sem copiar corpo das conversas para eventos de auditoria.

A redação por padrões não reconhece todo nome, endereço, dado sensível ou condição particular em linguagem natural. O operador deve fornecer os nomes/identificadores em `redaction_terms`, revisar o conteúdo tratado e remover o que faltar antes de publicar. Turnos com grande expansão por marcadores são limitados a 12.000 caracteres e sinalizados como truncados para revisão.

## Ainda pendente

- Tela de login/painel do superadministrador e conexão do frontend às novas APIs. A API/CLI estão implementadas; nenhuma tela foi criada nesta entrega.
- Upload/parser nativo TXT/ZIP/PDF; nesta etapa somente JSON normalizado, enviado como corpo da requisição.
- Extração assistida por LLM, filas, busca semântica/pgvector e consumo efetivo pela IA vendedora.
- Biblioteca privada de cada empresa e editor de políticas comerciais; os dados operacionais existentes continuam isolados e não são publicados por este módulo.
- Integrações operacionais WhatsApp/GestãoClick no painel de cada cliente.
- Gestão das credenciais OpenAI, custos e limites de uso da plataforma.
- Interface de rejeição/arquivamento de importações e política de retenção/LGPD completa.

## Provisionamento

Aplicar a migration e criar uma conta escolhida pelo operador. Não existem conta padrão ou senha gerada no código:

```bash
.venv/bin/alembic upgrade head
.venv/bin/python -m app.cli.platform_admin --email seu-email@empresa.com.br --name "Seu nome"
```

A senha é solicitada com getpass, confirmada e precisa ter 12–128 caracteres; não é passada pela linha de comando. E-mail existente não tem senha substituída. Requer acesso administrativo ao servidor e ao banco configurado. Não promover usuários de tenant por edição de role.

A autenticação da plataforma usa cookie `atendehub_platform_session`, HttpOnly, SameSite=Lax e Path=/api/v1/platform, com Secure em produção. As rotas de empresas continuam usando o cookie anterior, sem mudança de contrato. O proxy Next atual não encaminha as rotas/cookie da plataforma; isso será implementado junto ao painel próprio.

## Conteúdo proposto para o Dashboard do superadministrador (não implementado)

- Empresas: ativas, em teste e testes próximos do vencimento.
- Planos/assinaturas: distribuição por plano e pendências, quando o módulo financeiro estiver validado.
- IA: consumo, custo por empresa e falhas de processamento, quando existir instrumentação real.
- Conhecimento: importações, rascunhos aguardando revisão, versões publicadas e desativadas.
- Atividades: novas empresas, alterações administrativas e publicações.
- Menu: Dashboard, Empresas, Planos, Consumo de IA, Base de conhecimento, Importações, Auditoria e Configurações.

Não preencher indicadores com dados fictícios em produção. O Dashboard do cliente continua sendo operacional da própria distribuidora.
