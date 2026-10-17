import js from "@eslint/js";
export default [
  js.configs.recommended,
  { languageOptions: { globals: { document: "readonly", fetch: "readonly" } }, ignores: ["dist/**"] },
];
