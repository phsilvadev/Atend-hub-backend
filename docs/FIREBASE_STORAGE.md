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
O bucket foi configurado localmente em 06/nov/2026. O teste encontrou `DefaultCredentialsError`: o ambiente ainda não tem identidade de serviço disponível. Upload real permanece pendente; não foi enviado nenhum arquivo ao bucket real.

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
