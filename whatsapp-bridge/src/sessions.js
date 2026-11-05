import makeWASocket, {
  initAuthCreds,
  proto,
  normalizeMessageContent,
  DisconnectReason,
} from "@whiskeysockets/baileys";
import QRCode from "qrcode";
import { webVersion } from "./version.js";
import pino from "pino";
import { HttpsProxyAgent } from "https-proxy-agent";
const logger = pino({ level: "silent" });
const proxyUrl = process.env.HTTPS_PROXY || process.env.HTTP_PROXY;
const networkAgent = proxyUrl ? new HttpsProxyAgent(proxyUrl) : undefined;
export class Sessions {
  constructor(
    store,
    enqueue,
    factory = makeWASocket,
    versionProvider = webVersion,
  ) {
    this.store = store;
    this.enqueue = enqueue;
    this.factory = factory;
    this.versionProvider = versionProvider;
    this.sessions = new Map();
  }
  view(id) {
    const item = this.sessions.get(id);
    if (!item)
      return {
        status: "disconnected",
        qr_data_url: null,
        qr_expires_at: null,
        phone: null,
      };
    const fresh = item.qr_expires_at > Date.now() / 1000;
    return {
      status: item.status === "qr" && !fresh ? "connecting" : item.status,
      qr_data_url: fresh ? item.qr_data_url : null,
      qr_expires_at: fresh ? item.qr_expires_at : null,
      phone: item.phone || null,
    };
  }
  async start(id) {
    let item = this.sessions.get(id);
    if (item?.starting) return item.starting;
    if (item?.socket && ["connected", "connecting", "qr"].includes(item.status))
      return this.view(id);
    if (!item) {
      item = { status: "connecting", phone: null, stopped: false, retries: 0 };
      this.sessions.set(id, item);
    }
    if (item.socket) {
      item.socket.end(new Error("Restarting connection"));
      item.socket = null;
    }
    item.stopped = false;
    item.starting = this.open(id, item)
      .then(() => this.view(id))
      .catch(() => {
        item.status = "error";
        throw new Error("Connection unavailable");
      })
      .finally(() => {
        item.starting = null;
      });
    return item.starting;
  }
  async open(id, item) {
    const version = await this.versionProvider();
    const persisted = await this.store.read("session-" + id);
    if (item.stopped) return;
    const data = persisted || { creds: initAuthCreds(), keys: {} };
    let sock;
    const save = () =>
      item.stopped || (sock && item.socket !== sock)
        ? Promise.resolve()
        : this.store.write("session-" + id, data);
    const auth = {
      creds: data.creds,
      keys: {
        get: async (type, ids) =>
          Object.fromEntries(
            ids.map((key) => {
              let value = data.keys[type]?.[key];
              if (type === "app-state-sync-key" && value)
                value = proto.Message.AppStateSyncKeyData.fromObject(value);
              return [key, value];
            }),
          ),
        set: async (values) => {
          for (const [type, keys] of Object.entries(values)) {
            data.keys[type] ??= {};
            for (const [key, value] of Object.entries(keys)) {
              if (value) data.keys[type][key] = value;
              else delete data.keys[type][key];
            }
          }
          await save();
        },
      },
    };
    item.status = "connecting";
    sock = this.factory({
      auth,
      logger,
      version,
      agent: networkAgent,
      fetchAgent: networkAgent,
      printQRInTerminal: false,
      markOnlineOnConnect: false,
      syncFullHistory: false,
      shouldSyncHistoryMessage: () => false,
      shouldIgnoreJid: (jid) =>
        jid.endsWith("@g.us") || jid === "status@broadcast",
      qrTimeout: 45000,
      connectTimeoutMs: 20000,
    });
    item.socket = sock;
    sock.ev.on("creds.update", (updates) => {
      if (item.stopped || item.socket !== sock) return;
      Object.assign(data.creds, updates);
      save().catch(() => {
        item.status = "error";
        sock.end(new Error("Persistence unavailable"));
      });
    });
    sock.ev.on(
      "connection.update",
      async ({ connection, lastDisconnect, qr }) => {
        if (item.stopped || item.socket !== sock) return;
        if (qr) {
          const image = await QRCode.toDataURL(qr, { width: 280, margin: 2 });
          if (item.stopped || item.socket !== sock) return;
          item.qr_data_url = image;
          item.qr_expires_at = Math.floor(Date.now() / 1000) + 45;
          item.status = "qr";
        }
        if (connection === "open") {
          item.status = "connected";
          item.qr_data_url = null;
          item.qr_expires_at = null;
          item.retries = 0;
          const phone = sock.user?.id?.split(":")[0]?.split("@")[0];
          item.phone = /^\d{10,15}$/.test(phone || "") ? phone : null;
        }
        if (connection === "close") {
          item.socket = null;
          item.qr_data_url = null;
          item.qr_expires_at = null;
          item.phone = null;
          const code = lastDisconnect?.error?.output?.statusCode;
          if (code === DisconnectReason.loggedOut) {
            item.status = "disconnected";
            await this.store.remove("session-" + id);
            return;
          }
          item.retries++;
          if (item.retries > 5) {
            item.status = "error";
            return;
          }
          item.status = "connecting";
          item.timer = setTimeout(
            () => {
              if (!item.stopped) this.start(id).catch(() => {});
            },
            Math.min(30000, 1000 * 2 ** item.retries),
          );
        }
      },
    );
    sock.ev.on("messages.upsert", async ({ messages, type }) => {
      if (type !== "notify" || item.stopped || item.socket !== sock) return;
      for (const message of messages) {
        if (message.key.fromMe) continue;
        const jid = message.key.remoteJidAlt || message.key.remoteJid || "";
        if (!/^\d{10,15}@s\.whatsapp\.net$/.test(jid)) continue;
        const content = normalizeMessageContent(message.message);
        const body =
          content?.conversation || content?.extendedTextMessage?.text;
        if (
          typeof body !== "string" ||
          !body.length ||
          body.length > 4096 ||
          !message.key.id
        )
          continue;
        try {
          await this.enqueue({
            session_id: id,
            external_id: message.key.id,
            sender: jid.split("@")[0],
            name: (message.pushName || "").slice(0, 120),
            body,
            timestamp:
              Number(message.messageTimestamp) || Math.floor(Date.now() / 1000),
          });
        } catch {
          item.status = "error";
          sock.end(new Error("Inbox persistence unavailable"));
        }
      }
    });
  }
  async stop(id) {
    const item = this.sessions.get(id);
    if (item) {
      item.stopped = true;
      clearTimeout(item.timer);
      await item.starting?.catch(() => {});
      try {
        await item.socket?.logout();
      } catch {
      } finally {
        item.socket?.end(new Error("Disconnected by administrator"));
      }
      this.sessions.delete(id);
    }
    await this.store.remove("session-" + id);
    for (const name of await this.store.list("event")) {
      const event = await this.store.read(name);
      if (event?.session_id === id) await this.store.remove(name);
    }
    return this.view(id);
  }
}
