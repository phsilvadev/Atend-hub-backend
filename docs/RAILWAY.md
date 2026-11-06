# Railway — preparação da publicação

Projeto criado (privado): https://railway.com/project/788b8406-d900-4f19-a159-fd7d4ff96338

Ambiente: `production`, ID `4a1b16bf-fd6b-4e12-ba35-1e3824c2adbb`.

| Serviço vazio | Repositório previsto / branch | Domínio reservado |
|---|---|---|
| api | phsilvadev/Atend-hub-backend / development | api-production-5aaf.up.railway.app |
| cliente | phsilvadev/consistent-design-system / development | cliente-production-a80d.up.railway.app |
| superadmin | phsilvadev/super-admin-atendehub / development | superadmin-production-3d47.up.railway.app |

IDs de serviços: API `66fc04cb-4ae4-49fc-b064-10f04110611d`, cliente `3ca8c8fd-e8d3-4978-b9f4-4995277ac315`, superadmin `a5e024d2-c810-495c-9168-50cbbff7a411`. Domínios reservados para porta 8080; não há fonte associada/deployment da aplicação ainda. Não confundir serviço/domínio criado com aplicação publicada.

## Pré-requisitos à primeira publicação
1. Site Key e Secret Key reais do Turnstile no backend; registrar os hostnames cliente e superadmin acima no widget Cloudflare. APP_ENV=production não aceita dummy keys.
2. Provisionar PostgreSQL persistente, configurar driver/URL, aplicar e validar migrations nele. Não publicar SQLite em disco efêmero. SQLite de desenvolvimento não deve ser enviado como banco inicial nem populado em produção com fixtures.
3. Configurar origens HTTPS explícitas no backend, cookies seguros, chaves de criptografia persistentes e credencial Firebase por mecanismo seguro do serviço. O arquivo de credencial local em /workspace não existe automaticamente no Railway.
4. Associar cada repo/branch correta após configurar as variáveis. Frontends precisam de BACKEND_URL e APP_ORIGIN próprios; comando deve ouvir 0.0.0.0:$PORT. Builder Railpack; nenhum Docker local é necessário.
5. Configurar migrations antes da aplicação iniciar, healthcheck backend /health e validar status terminal SUCCESS/HTTP, cadastro/login/antirrobô, cookies, isolamento e imagem real. Não semear administradores com senhas de demonstração nem planos fictícios em produção.

Nenhuma credencial é registrada neste documento. Preparação não é autorização para desligar o antirrobô, usar chaves de teste em produção ou abrir o Storage publicamente.
