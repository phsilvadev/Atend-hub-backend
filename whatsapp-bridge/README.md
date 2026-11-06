# Gateway WhatsApp por QR Code

Serviço Node 22+ do backend, baseado no Baileys 6.7.23, independente da Cloud API Meta. Não é uma integração oficial. Cada empresa possui um ID de sessão aleatório gerenciado exclusivamente pela API. Sem envio de mensagens nesta etapa.

```bash
cd whatsapp-bridge
npm ci
cp .env.example .env
# Configure BRIDGE_TOKEN, BRIDGE_ENCRYPTION_KEY e BACKEND_CALLBACK_URL.
npm start
```

O `BRIDGE_TOKEN` (pelo menos 32 caracteres aleatórios) deve coincidir com `WHATSAPP_QR_BRIDGE_TOKEN` na API. Gere os dois segredos localmente; não copie valores dos testes. `BRIDGE_ENCRYPTION_KEY` é uma chave de 32 bytes em base64, mantida no gerenciador de segredos. Pode gerar com `node -e "console.log(require('crypto').randomBytes(32).toString('base64'))"`. Não expor segredos via NEXT_PUBLIC, logs ou Git.

O serviço escuta **somente 127.0.0.1:8300** por padrão. Não disponibilize diretamente ao navegador. API e gateway na mesma máquina podem usar HTTP localhost; para acesso remoto use proxy privado HTTPS autenticado por Bearer. Não há CORS e requisições com Origin são rejeitadas. Configure portas conforme a hospedagem, sem Docker obrigatório.

Estado persistente em `BRIDGE_STATE_DIR` (padrão `state/`), diretório privado 0700 e arquivos 0600. Chaves Signal/credenciais e outbox são criptografados com AES-256-GCM e nonce aleatório. QR Code fica apenas em memória, expira e não vai para logs/arquivos. Escritas são serializadas por arquivo e substituídas atomicamente. Use uma única instância por diretório; não é um serviço distribuído. Preserve a chave de criptografia com segurança e mantenha backups protegidos; trocar/perder a chave exige novo pareamento. Não há rotação automática implementada.

Rotas internas do gateway, todas exigindo Bearer:
- `POST /sessions/{uuid}`: iniciar/reutilizar sessão, retorna status/QR PNG/validade/número.
- `GET /sessions/{uuid}`: consultar sem criar sessão.
- `DELETE /sessions/{uuid}`: logout quando disponível, apagar material local e bloquear socket. Se o celular continuar listando um dispositivo offline, remova também em Dispositivos conectados.

`messages.upsert` tipo notify recebe apenas textos individuais com telefone identificável. Não importa histórico, grupos, status, mensagens próprias, áudios ou imagens. IDs LID sem telefone correspondente são ignorados nesta versão, sem inventar telefone. A outbox criptografada reenvia callbacks a cada 2s com timestamp recente e HMAC; a API deduplica mensagens. Em falha de disco/lotação o socket é interrompido: monitore disco, tamanho da fila e processo em produção. Não há garantia de captura de mensagens durante indisponibilidade do serviço; histórico/reconciliação não foi implementado. Reconexão usa até cinco tentativas com backoff; ao esgotar, reinicie pelo painel.

Teste de armazenamento/isolamento/ciclo e autenticação HTTP: `npm test`. Os testes não pareiam um celular real. Referências: https://baileys.wiki/docs/intro/ e https://github.com/WhiskeySockets/Baileys (eventos connection.update, creds.update e messages.upsert). O código não importa o SDK oficial Meta nem solicita credenciais Meta ao cliente.

A versão de protocolo é consultada no WhatsApp Web, com fallback da biblioteca e cache de uma hora; não é uma troca automática da versão npm. Em incompatibilidade do protocolo, o operador pode configurar `WA_WEB_VERSION=major,minor,revision` com uma versão validada. Não use números de versão arbitrários. `HTTPS_PROXY`/`HTTP_PROXY` são respeitados pelo WebSocket e pela consulta de versão; TLS continua validado. Logs diretos do libsignal são suprimidos no processo para evitar exposição das chaves de sessão. O processo emite somente mensagens genéricas de inicialização/falha.

## Railway

Publicar esta pasta como raiz de um serviço Node 22 separado (`railway up whatsapp-bridge --path-as-root`). Configure `BRIDGE_HOST=0.0.0.0`, `PORT=8300`, `BRIDGE_STATE_DIR=/data/state` e volume persistente em `/data`, com uma única réplica. O padrão local continua restrito a localhost. `/health` retorna somente estado do processo, sem autenticação, para o healthcheck; as rotas de sessão continuam exigindo Bearer e recusando Origin.

Configure o domínio HTTPS do gateway em `WHATSAPP_QR_BRIDGE_URL` na API e o mesmo segredo em `BRIDGE_TOKEN`/`WHATSAPP_QR_BRIDGE_TOKEN`. O callback deve apontar para a API pública HTTPS em `/api/v1/webhooks/whatsapp-qr`; eventos são assinados com HMAC. `BRIDGE_ENCRYPTION_KEY` fica somente no serviço e deve ser preservada entre deployments. Não disponibilize token nem chave no frontend. Reiniciar apenas Next/API não inicia este gateway.
