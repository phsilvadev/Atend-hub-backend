import test from "node:test";
import assert from "node:assert/strict";
import { parseVersion } from "../src/version.js";
test("Validates protocol override without accepting code or invalid integers", () => {
  assert.deepEqual(parseVersion("2,3000,1234567890"), [2, 3000, 1234567890]);
  for (const value of [
    "2,3000",
    "[2,3000,1]",
    "2,3000,evil",
    "2,3000,9999999999",
  ])
    assert.throws(() => parseVersion(value));
});
