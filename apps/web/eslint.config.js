import js from "@eslint/js";
import tseslint from "typescript-eslint";
export default [
  { ignores: ["dist/**"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  { files: ["src/**/*.{ts,tsx}"], languageOptions: { globals: { document: "readonly", fetch: "readonly" } } },
];
