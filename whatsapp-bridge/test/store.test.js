import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { randomBytes } from "node:crypto";
import { Store } from "../src/store.js";

test("Encrypts signal buffers, serializes writes, rejects traversal and wrong key", async () => {
  const root = await mkdtemp(join(tmpdir(), "qr-store-"));
  try {
    const store = new Store(root, randomBytes(32).toString("base64"));
    await store.init();
    await Promise.all([
      store.write("session-abc", {
        password: "private-material",
        key: Buffer.from("signal"),
      }),
      store.write("session-abc", {
        password: "last-material",
        key: Buffer.from("signal"),
      }),
    ]);
    const raw = await readFile(join(root, "session-abc.bin"));
    assert.equal(raw.includes("material"), false);
    const data = await store.read("session-abc");
    assert.equal(data.password, "last-material");
    assert.equal(Buffer.isBuffer(data.key), true);
    assert.throws(() => store.path("../secret"));
    const other = new Store(root, randomBytes(32).toString("base64"));
    await assert.rejects(other.read("session-abc"));
    await store.remove("session-abc");
    assert.equal(await store.read("session-abc"), null);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
