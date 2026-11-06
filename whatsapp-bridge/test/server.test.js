import test from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { randomBytes } from "node:crypto";
import { createServer } from "node:net";

test("Gateway authenticates internal calls, rejects browser origins and arbitrary session paths", async () => {
  const reservation = createServer();
  reservation.listen(0, "127.0.0.1");
  await once(reservation, "listening");
  const port = reservation.address().port;
  await new Promise((resolve) => reservation.close(resolve));
  const root = await mkdtemp(join(tmpdir(), "bridge-test-")),
    token = "test-only-server-key-with-32-characters";
  const child = spawn(process.execPath, ["src/server.js"], {
    env: {
      ...process.env,
      PORT: String(port),
      BRIDGE_HOST: "0.0.0.0",
      BRIDGE_TOKEN: token,
      BRIDGE_ENCRYPTION_KEY: randomBytes(32).toString("base64"),
      BRIDGE_PORT: String(port),
      BRIDGE_STATE_DIR: root,
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  try {
    await Promise.race([
      once(child.stdout, "data"),
      once(child, "exit").then(() => {
        throw new Error("Gateway failed to start");
      }),
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error("Gateway timeout")), 5000).unref(),
      ),
    ]);
    const url = `http://127.0.0.1:${port}/sessions/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa`;
    const health = await fetch(`http://127.0.0.1:${port}/health`);
    assert.equal(health.status, 200);
    assert.deepEqual(await health.json(), { status: "ok" });
    assert.equal((await fetch(url)).status, 401);
    assert.equal(
      (
        await fetch(url, {
          headers: {
            Authorization: "Bearer " + token,
            Origin: "https://browser.example",
          },
        })
      ).status,
      401,
    );
    const result = await fetch(url, {
      headers: { Authorization: "Bearer " + token },
    });
    assert.equal(result.status, 200);
    assert.equal((await result.json()).status, "disconnected");
    assert.equal(result.headers.get("cache-control"), "no-store");
    assert.equal(
      (
        await fetch(`http://127.0.0.1:${port}/sessions/other`, {
          headers: { Authorization: "Bearer " + token },
        })
      ).status,
      404,
    );
  } finally {
    child.kill("SIGTERM");
    await once(child, "exit");
    await rm(root, { recursive: true, force: true });
  }
});
