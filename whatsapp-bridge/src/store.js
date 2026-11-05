import {
  mkdir,
  readFile,
  writeFile,
  rename,
  unlink,
  readdir,
} from "node:fs/promises";
import { join } from "node:path";
import { createCipheriv, createDecipheriv, randomBytes } from "node:crypto";
import { BufferJSON } from "@whiskeysockets/baileys";

export class Store {
  constructor(root, key) {
    this.root = root;
    this.key = Buffer.from(key, "base64");
    if (this.key.length !== 32)
      throw new Error(
        "BRIDGE_ENCRYPTION_KEY must be 32 random bytes in base64",
      );
    this.writes = new Map();
  }
  async init() {
    await mkdir(this.root, { recursive: true, mode: 0o700 });
  }
  path(name) {
    if (!/^[a-z]+-[a-z0-9-]+$/.test(name))
      throw new Error("Invalid state name");
    return join(this.root, name + ".bin");
  }
  async read(name) {
    try {
      const raw = await readFile(this.path(name));
      const cipher = createDecipheriv(
        "aes-256-gcm",
        this.key,
        raw.subarray(0, 12),
      );
      cipher.setAuthTag(raw.subarray(12, 28));
      return JSON.parse(
        Buffer.concat([
          cipher.update(raw.subarray(28)),
          cipher.final(),
        ]).toString(),
        BufferJSON.reviver,
      );
    } catch (error) {
      if (error.code === "ENOENT") return null;
      throw error;
    }
  }
  async write(name, data) {
    // Snapshot before queuing: signal-key writes must not race or lose updates.
    const json = JSON.stringify(data, BufferJSON.replacer);
    const pending = (this.writes.get(name) || Promise.resolve())
      .catch(() => {})
      .then(async () => {
        const iv = randomBytes(12),
          cipher = createCipheriv("aes-256-gcm", this.key, iv);
        const encrypted = Buffer.concat([cipher.update(json), cipher.final()]);
        const target = this.path(name),
          temporary = target + ".tmp";
        await writeFile(
          temporary,
          Buffer.concat([iv, cipher.getAuthTag(), encrypted]),
          { mode: 0o600 },
        );
        await rename(temporary, target);
      });
    this.writes.set(name, pending);
    try {
      await pending;
    } finally {
      if (this.writes.get(name) === pending) this.writes.delete(name);
    }
  }
  async remove(name) {
    await this.writes.get(name)?.catch(() => {});
    await unlink(this.path(name)).catch((error) => {
      if (error.code !== "ENOENT") throw error;
    });
  }
  async list(prefix) {
    return (await readdir(this.root))
      .filter((name) => name.startsWith(prefix + "-") && name.endsWith(".bin"))
      .map((name) => name.slice(0, -4));
  }
}
