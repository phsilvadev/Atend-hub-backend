import { createServer } from "node:http";
import {
  createHash,
  timingSafeEqual,
  createHmac,
  randomUUID,
} from "node:crypto";
import { resolve } from "node:path";
import { Store } from "./store.js";
import { Sessions } from "./sessions.js";

// libsignal has direct console calls that include private session keys.
// This dedicated process emits only controlled, generic lifecycle messages.
for (const method of ["log", "info", "warn", "error", "debug", "dir", "trace"])
  console[method] = () => {};
process.on("uncaughtException", () => {
  process.stderr.write("Gateway stopped after an internal failure.\n");
  process.exit(1);
});
process.on("unhandledRejection", () => {
  process.stderr.write("Gateway stopped after an internal failure.\n");
  process.exit(1);
});
const token = process.env.BRIDGE_TOKEN || "";
if (token.length < 32)
  throw new Error("BRIDGE_TOKEN must have at least 32 characters");
const callback = new URL(
  process.env.BACKEND_CALLBACK_URL ||
    "http://127.0.0.1:8000/api/v1/webhooks/whatsapp-qr",
);
if (
  callback.protocol !== "https:" &&
  !(
    callback.protocol === "http:" &&
    ["127.0.0.1", "localhost", "[::1]"].includes(callback.hostname)
  )
)
  throw new Error("Callback requires HTTPS or localhost");
if (callback.username || callback.password)
  throw new Error("Callback cannot contain credentials");
const store = new Store(
  resolve(process.env.BRIDGE_STATE_DIR || "state"),
  process.env.BRIDGE_ENCRYPTION_KEY || "",
);
await store.init();
const sessions = new Sessions(store, (event) =>
  store.write("event-" + randomUUID(), event),
);
let draining = false;
async function drain() {
  if (draining) return;
  draining = true;
  try {
    for (const name of await store.list("event")) {
      const event = await store.read(name);
      if (!event) continue;
      const timestamp = String(Math.floor(Date.now() / 1000)),
        body = JSON.stringify(event);
      const signature = createHmac("sha256", token)
        .update(timestamp + "." + body)
        .digest("hex");
      try {
        const response = await fetch(callback, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "x-bridge-timestamp": timestamp,
            "x-bridge-signature": signature,
          },
          body,
          signal: AbortSignal.timeout(8000),
          redirect: "error",
        });
        if (response.ok) await store.remove(name);
        else break; // Durable encrypted outbox, retry on the next cycle.
      } catch {
        break;
      }
    }
  } finally {
    draining = false;
  }
}
setInterval(() => drain().catch(() => {}), 2000).unref();
const server = createServer(async (req, res) => {
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("Content-Type", "application/json");
  const send = (status, data) => {
    res.writeHead(status);
    res.end(JSON.stringify(data));
  };
  if (req.method === "GET" && req.url === "/health")
    return send(200, { status: "ok" });
  const supplied = req.headers.authorization || "";
  if (
    req.headers.origin ||
    !timingSafeEqual(
      createHash("sha256").update(supplied).digest(),
      createHash("sha256")
        .update("Bearer " + token)
        .digest(),
    )
  )
    return send(401, { error: "Unauthorized" });
  const match =
    /^\/sessions\/([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})$/.exec(
      req.url || "",
    );
  if (!match) return send(404, { error: "Not found" });
  try {
    if (req.method === "GET") return send(200, sessions.view(match[1]));
    if (req.method === "POST") {
      sessions.start(match[1]).catch(() => {});
      return send(200, sessions.view(match[1]));
    }
    if (req.method === "DELETE")
      return send(200, await sessions.stop(match[1]));
    return send(405, { error: "Method not allowed" });
  } catch {
    return send(503, { error: "Connection unavailable" });
  }
});
server.listen(Number(process.env.PORT || process.env.BRIDGE_PORT || 8300), process.env.BRIDGE_HOST || "127.0.0.1", () =>
  process.stdout.write("WhatsApp gateway listening\n"),
);
// Restore existing paired sessions from encrypted storage, without importing history.
for (const name of await store.list("session")) {
  const id = name.slice(8);
  if (/^[a-f0-9-]{36}$/.test(id)) sessions.start(id).catch(() => {});
}
