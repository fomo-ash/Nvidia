import js from "@eslint/js";
import tseslint from "typescript-eslint";
export default [
  { ignores: ["dist/**", "src/services/schema.d.ts"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  { files: ["src/**/*.{ts,tsx}"], languageOptions: { globals: { document: "readonly", fetch: "readonly", AbortController: "readonly", AbortSignal: "readonly" } } },
  { files: ["scripts/*.mjs"], languageOptions: { globals: { process: "readonly", URL: "readonly" } } },
];
