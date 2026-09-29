// MapLibre 6 loads its web worker from a URL next to its own module file, which does
// not exist once Next bundles the library. We serve the worker (and the chunk it
// imports) from /public/maplibre and point MapLibre at it with setWorkerUrl().
import { copyFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const dist = path.join(path.dirname(require.resolve("maplibre-gl/package.json")), "dist");
const out = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../public/maplibre");
mkdirSync(out, { recursive: true });
for (const f of ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"]) copyFileSync(path.join(dist, f), path.join(out, f));
console.log("maplibre worker copied to public/maplibre");
