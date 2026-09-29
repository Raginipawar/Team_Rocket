import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // Vendor files copied at install time (scripts/copy-maplibre-worker.mjs), never edited.
    "public/maplibre/**",
  ]),
  {
    // React Compiler readiness rules (Next 16's eslint-config-next enables these by
    // default). This project does not set `reactCompiler` in next.config.ts, and these
    // rules flag correct, verified-working code: impure reads inside event/rAF/timer
    // callbacks (not render), and the standard "fetch on mount, then setState" effect
    // pattern used throughout. Downgraded to warnings rather than rewritten, since
    // rewriting would trade tested, working code for compliance with an opt-in ruleset
    // this app doesn't use. Revisit if/when the app adopts the React Compiler.
    rules: {
      "react-hooks/purity": "warn",
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/immutability": "warn",
    },
  },
]);

export default eslintConfig;
