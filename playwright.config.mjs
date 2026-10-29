import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  timeout: 120000,
  use: { channel: process.env.PLAYWRIGHT_CHANNEL || undefined, baseURL: "http://localhost:5173", trace: "off", screenshot: "off" },
  reporter: "list",
});
