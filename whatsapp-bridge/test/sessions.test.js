import test from "node:test";
import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { Sessions } from "../src/sessions.js";
import { setTimeout } from "node:timers/promises";

test("QR is short lived, never persisted, isolates sessions, filters groups/self/history", async () => {
  const events = [],
    saved = [];
  const store = {
    read: async () => null,
    write: async (name, data) => saved.push(name),
    remove: async () => {},
    list: async () => [],
  };
  let socket;
  const factory = () => {
    socket = {
      ev: new EventEmitter(),
      user: { id: "5511999999999:1@s.whatsapp.net" },
      logout: async () => {},
      end: () => {},
    };
    return socket;
  };
  const sessions = new Sessions(
    store,
    async (event) => events.push(event),
    factory,
    async () => [2, 3000, 1],
  );
  await sessions.start("first");
  const first = socket;
  first.ev.emit("connection.update", {
    qr: "not-a-real-pairing-code-test-only",
  });
  for (let i = 0; i < 50 && sessions.view("first").status !== "qr"; i++)
    await setTimeout(10);
  assert.equal(sessions.view("first").status, "qr");
  assert.match(sessions.view("first").qr_data_url, /^data:image\/png;base64,/);
  assert.equal(saved.length, 0);
  assert.equal(sessions.view("second").qr_data_url, null);
  sessions.sessions.get("first").qr_expires_at = 1;
  assert.equal(sessions.view("first").qr_data_url, null);
  first.ev.emit("connection.update", { connection: "open" });
  assert.equal(sessions.view("first").phone, "5511999999999");
  const message = {
    key: { id: "inbound", remoteJid: "5511888888888@s.whatsapp.net" },
    message: { conversation: "Preciso de chapas" },
    pushName: "Cliente",
    messageTimestamp: 123,
  };
  first.ev.emit("messages.upsert", { type: "append", messages: [message] });
  first.ev.emit("messages.upsert", {
    type: "notify",
    messages: [
      { ...message, key: { ...message.key, fromMe: true } },
      { ...message, key: { ...message.key, remoteJid: "group@g.us" } },
      message,
    ],
  });
  await setTimeout(10);
  assert.equal(events.length, 1);
  assert.equal(events[0].session_id, "first");
  await sessions.start("second");
  await sessions.stop("first");
  assert.equal(sessions.view("first").status, "disconnected");
  assert.equal(sessions.view("second").status, "connecting");
  await sessions.stop("second");
});
