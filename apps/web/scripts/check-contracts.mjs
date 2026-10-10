// Fails if lib/enums.ts drifts from packages/contracts/enums.json (the single definition).
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const jsonPath = path.resolve(here, "../../../packages/contracts/enums.json");
const tsPath = path.resolve(here, "../lib/enums.ts");

// A platform deploy (Vercel) only ships apps/web, not the whole monorepo --
// packages/contracts/enums.json lives outside that tree, so it's genuinely
// absent there, not drifted. Skip rather than fail the build; this check
// still runs (and still means something) on a real local/monorepo checkout.
if (!existsSync(jsonPath)) {
  console.log("contracts check skipped: packages/contracts/enums.json not present in this build (not a full monorepo checkout)");
  process.exit(0);
}

const contract = JSON.parse(readFileSync(jsonPath, "utf8"));
const ts = readFileSync(tsPath, "utf8");
const block = ts.slice(ts.indexOf("export const ENUMS = {"), ts.indexOf("} as const;"));

let failed = false;
for (const [name, values] of Object.entries(contract)) {
  const m = block.match(new RegExp(`\\b${name}: \\[([\\s\\S]*?)\\]`));
  if (!m) {
    console.error(`missing enum ${name} in lib/enums.ts`);
    failed = true;
    continue;
  }
  const mine = [...m[1].matchAll(/"([^"]+)"/g)].map((x) => x[1]);
  if (JSON.stringify(mine) !== JSON.stringify(values)) {
    console.error(`enum ${name} differs:\n  contract: ${values.join(", ")}\n  web:      ${mine.join(", ")}`);
    failed = true;
  }
}
if (failed) process.exit(1);
console.log(`contracts ok: ${Object.keys(contract).length} enums match packages/contracts/enums.json`);
