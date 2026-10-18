import { readFileSync, writeFileSync } from "node:fs";
import openapiTS, { astToString } from "openapi-typescript";

const schema = new URL("../../api/openapi.json", import.meta.url);
const target = new URL("../src/services/schema.d.ts", import.meta.url);
const generated = astToString(await openapiTS(schema));
if (process.argv.includes("--write")) {
  writeFileSync(target, generated);
} else if (readFileSync(target, "utf8") !== generated) {
  throw new Error("API types are stale. Run pnpm contracts:generate.");
}
