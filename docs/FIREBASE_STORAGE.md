# Imagens de produtos — Firebase Storage

## Fluxo implementado
A aplicação usa sessões próprias; não exige Firebase Auth no navegador. Administradores enviam a imagem à rota Next, que encaminha o binário à API autenticada. FastAPI verifica a empresa/produto, versão e arquivo; reprocessa para WebP e grava num objeto privado usando Firebase Admin SDK. Leitura também passa pela API e exige sessão ativa da mesma empresa. Vendedores podem visualizar; somente administradores enviam/substituem.

Caminho gerado somente no servidor: `companies/{company_id}/products/{product_id}/{uuid}.webp`. Não usamos nomes fornecidos pelo usuário, URLs públicas, download tokens, `make_public`, chaves no frontend ou permissões de upload anônimo. A consulta do catálogo devolve apenas `has_image`, `image_version`, `image_updated_at` e `image_upload_enabled` (este último indica que há um bucket configurado; não comprova credencial/IAM).

## Configurar no backend
No `.env` do backend:
```dotenv
FIREBASE_STORAGE_BUCKET=atende-ia-6d09f.firebasestorage.app
GOOGLE_APPLICATION_CREDENTIALS=/caminho/fora-do-repositorio/firebase-service-account.json
```
Bucket e credencial local configurados em 06/nov/2026. A credencial fornecida foi instalada fora dos repositórios em diretório com permissão 700/arquivo 600, e seu caminho foi registrado somente no .env ignorado pelo Git. O bloqueio anterior DefaultCredentialsError foi resolvido. Upload/leitura pelo navegador e acesso negado entre empresas foram validados com Firebase real; o objeto temporário foi excluído e a ausência confirmada. O acesso anônimo direto retornou 403 AccessDenied, sem token público no objeto. Isso valida o objeto criado, sem alegar revisão de todas as regras/IAM do projeto.

Para desenvolvimento, em Firebase Console → Configurações do projeto → Contas de serviço, gere uma credencial de serviço para o backend e mantenha o JSON fora do repositório, com acesso restrito ao processo. Informe somente o caminho no `.env`; o backend usa `credentials.Certificate` para esse caminho. Em infraestrutura com identidade de workload, deixe a variável vazia e use Application Default Credentials. Reinicie o backend após configurar/rotacionar a identidade. Não use `NEXT_PUBLIC_*` para a chave e não coloque o JSON no frontend.

A identidade precisa de acesso aos objetos desse bucket: criar, ler e excluir os objetos gerenciados pela aplicação (por exemplo, uma função IAM adequada de objetos limitada ao bucket). Não conceda papel Owner do projeto. `bucket.exists()` consulta metadados e pode exigir permissão adicional de bucket; não é requisito para o upload/download de objetos.

O bucket deve existir, com Cloud Storage/Firebase Storage habilitado e faturamento conforme os requisitos atuais do projeto. Mantenha acesso público bloqueado, sem concessões a `allUsers`/`allAuthenticatedUsers`. Regras sugeridas para um bucket dedicado estão em `docs/firebase/storage.rules`: negam acesso direto do cliente. Admin SDK usa IAM e não depende das regras Firebase do navegador. Se o projeto já tem outros usos, revise/mescle as regras; não substitua regras existentes sem avaliar esses usos.

## Limites e consistência
- JPG, PNG ou WebP estáticos; até 5 MiB de entrada, 20 megapixels e dimensão máxima de 10.000 pixels.
- Conteúdo é decodificado e MIME conferido. Imagens animadas/SVG/arquivos falsos são recusados. Reencodificação limita a 1600×1600 e remove EXIF/GPS/metadados e dados extras do original.
- Proxy e API limitam os bytes efetivamente recebidos. Limite de 20 tentativas de upload por empresa a cada 15 minutos. Se houver um proxy externo, permita corpos de 5 MiB e timeout compatível, sem remover os limites da aplicação.
- `image_version` evita sobrescrever envio concorrente. A sessão, papel e empresa são revalidados após o upload, antes de salvar o vínculo. Uma imagem rejeitada ou upload com erro preserva a anterior.
- Objeto novo é criado com condição de não existência; geração registrada no banco é usada nas leituras/exclusões. Após commit, a substituição remove a versão anterior. Falhas de exclusão geram somente `product_image_cleanup_pending`, sem dados sensíveis. Falhas/interrupções entre Storage e banco podem deixar órfãos: reconciliação periódica entre objetos e referências do banco ainda é uma tarefa operacional pendente; não aplicar expiração indiscriminada que apague imagens ativas.
- Sincronização GestãoClick não sobrescreve as imagens próprias da plataforma. Ainda não há remoção de foto, galeria, upload em lote ou sincronização de fotos do ERP.
- Imagens são privadas, com `Cache-Control: private, no-store`, sem cache compartilhado. Não podem ser compartilhadas por URL pública com clientes externos nesta etapa.

## Validação
Pytest cobre SDK simulado, validação real de imagens, isolamento, papéis, revogação durante upload, concorrência, falhas, substituição e preservação na importação ERP. E2E cobre Next → API → SDK simulado, arrastar/soltar, prévia, persistência, miniatura autenticada, mobile e CSRF. A fixture gráfica de produto é fictícia e existe somente nos testes. Nenhuma simulação é ativável por flag na API de produção.

Teste real reproduzível pelo frontend: `E2E_FIREBASE_REAL=1 E2E_GESTAOCLICK_STUB=1` com `BACKEND_SOURCE_DIR` explícito e credencial local configurada. O runner usa SQLite temporário; somente o ERP é simulado. A verificação/limpeza usa as referências desse banco/empresa de teste, nunca objetos de outras empresas. Não habilite E2E_FIREBASE_STORAGE_STUB junto ao modo real.

## Credencial no Railway
O backend também aceita `GOOGLE_SERVICE_ACCOUNT_JSON` como variável secreta com o JSON da conta de serviço. Esse valor é SecretStr e só é passado ao Firebase Admin SDK no servidor. É uma alternativa ao caminho GOOGLE_APPLICATION_CREDENTIALS, que não existe automaticamente no container. Em produção a variável JSON já foi configurada no serviço api, sem colocar o arquivo no Git ou no frontend. Ao configurar a variável JSON, ela tem precedência sobre arquivo/ADC.
