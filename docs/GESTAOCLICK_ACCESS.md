# GestãoClick: teste de acesso e seleção de loja

Fonte: OpenAPI 3.1.0 enviado pelo usuário em 06/11/2026. SHA-256 do arquivo original: `c38d58ac548290117f2209dbc78bd598c921d56ba1ea5d2e77f0bcb438e14424`.

Recorte versionado: [contrato de lojas](contracts/gestaoclick-stores.openapi.json). O arquivo completo não foi copiado para o repositório.

## Contrato confirmado

- Servidor principal: https://api.gestaoclick.com/api.
- Headers obrigatórios: access-token e secret-access-token. Nunca enviá-los ao browser após salvar.
- GET /lojas exige Lojas/index e retorna code/status/data, com id/nome de lojas acessíveis à chave.
- O texto específico de /lojas informa retorno sem paginação; o documento também inclui parâmetros globais de paginação. Neste recorte, a chamada é feita sem esses parâmetros.
- Erros documentados: 401 credenciais/acesso, 402 plano API, 403 permissão, 429 quota. Quota geral: 3 requisições/s e 30.000/dia por empresa no ERP.
- Listar lojas não comprova permissão para ler produtos/clientes nem identifica com segurança o usuário efetivo da chave. Conforme o documento, o default pode ser usuário master e loja matriz; configuração da chave e futuras consultas precisam respeitar esses vínculos.

## Implementado

Teste explícito após salvar, com as credenciais decifradas somente no backend. Host/path fixos do contrato, HTTPS, redirects desativados, timeout e resposta limitada a 1 MiB. Configurações antigas com outro servidor são preservadas, mas recusadas no teste antes de enviar credenciais. Nenhuma resolução/URL fornecida pelo cliente é usada no transporte.

O teste guarda somente lojas, data, erro normalizado e seleção existente se ela continuar autorizada. Em falha, apaga a lista/seleção anterior. Trocar tokens/endereço invalida a validação; salvar sem alteração de credenciais a preserva. Seleção aceita apenas ID presente na última consulta bem-sucedida, feita há até 15 minutos. Uma loja salva é preferência da integração, não alteração do vínculo fixo da chave no ERP.

Controle de concorrência por versão: uma resposta iniciada antes da edição/remoção da configuração é descartada. Autorização administrativa é revalidada antes de persistir. Sem lock de escrita durante o I/O externo. Limite local: uma tentativa por segundo e dez por quinze minutos por tenant; demais integrações da conta ERP também consomem a quota compartilhada.

## Ainda pendente

Credenciais reais autorizadas, verificação do usuário efetivo e das permissões de catálogo, compatibilidade da loja selecionada com o escopo da chave, preços/estoque e sincronização de produtos/clientes. Nenhum dado comercial é importado neste recorte. A prévia frontend permanece simulada e separada do painel real.
