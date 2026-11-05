import {
  fetchLatestWaWebVersion,
  fetchLatestBaileysVersion,
} from "@whiskeysockets/baileys";
import { HttpsProxyAgent } from "https-proxy-agent";
let cached,
  expires = 0;
export function parseVersion(value) {
  if (!/^\d{1,10},\d{1,10},\d{1,10}$/.test(value))
    throw new Error(
      "WA_WEB_VERSION must contain three comma-separated integers",
    );
  const version = value.split(",").map(Number);
  if (version.some((v) => !Number.isSafeInteger(v) || v < 0 || v > 4294967295))
    throw new Error("Invalid WhatsApp version");
  return version;
}
export async function webVersion() {
  if (process.env.WA_WEB_VERSION)
    return parseVersion(process.env.WA_WEB_VERSION);
  if (cached && Date.now() < expires) return cached;
  const proxy = process.env.HTTPS_PROXY || process.env.HTTP_PROXY;
  const options = {
    timeout: 5000,
    ...(proxy ? { httpsAgent: new HttpsProxyAgent(proxy), proxy: false } : {}),
  };
  const live = await fetchLatestWaWebVersion(options);
  const result = live.isLatest
    ? live
    : await fetchLatestBaileysVersion(options);
  cached = result.version;
  expires = Date.now() + 3600000;
  return cached;
}
