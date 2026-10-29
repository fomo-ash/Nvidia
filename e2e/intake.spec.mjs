import { existsSync, readFileSync } from "node:fs";
import { test, expect } from "@playwright/test";

const config = Object.fromEntries((existsSync(new URL("../.env", import.meta.url)) ? readFileSync(new URL("../.env", import.meta.url), "utf8") : "").split(/\r?\n/).filter(line => /^[A-Z_]+=/.test(line)).map(line => [line.slice(0, line.indexOf("=")), line.slice(line.indexOf("=") + 1).replace(/^["']|["']$/g, "")]));

test("operator signs in, recovers target drift, sees retained evidence, and recovers an expired session", async ({ page, context }) => {
  test.skip(!config.OPERATOR_SECRET || !config.SAMPLE_TARGET_UID, "Configure the local authenticated kind environment first");
  let stale = true;
  await page.route("**/api/v1/incident-targets", async route => {
    const response = await route.fetch();
    const targets = await response.json();
    if (stale) { targets[0].uid = "stale-browser-uid"; stale = false; }
    await route.fulfill({ response, json: targets });
  });
  await page.goto("/incidents");
  await page.getByLabel("Local operator secret").fill(config.OPERATOR_SECRET);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText(/UID: stale-browser-uid/)).toBeVisible();
  await page.getByRole("button", { name: "Report incident", exact: true }).click();
  await expect(page.getByText(/registered target changed/)).toBeVisible();
  await expect(page.getByText(new RegExp(config.SAMPLE_TARGET_UID))).toBeVisible();
  await page.getByRole("button", { name: "Refresh target", exact: true }).click();
  await page.getByLabel("Symptom summary").fill("Browser acceptance: sample requests return 5xx");
  await page.getByRole("button", { name: "Report incident", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Report progress" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Source observations" })).toBeVisible({ timeout: 90000 });
  await expect(page.getByText("Human review required. Infrastructure changes are not enabled.")).toBeVisible();
  await context.clearCookies();
  await page.getByRole("button", { name: "Report incident", exact: true }).click();
  await expect(page.getByText(/session expired. Sign in again before reporting/)).toBeVisible();
  await page.getByLabel("Local operator secret").fill(config.OPERATOR_SECRET);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText(/operator session active/)).toBeVisible();
});


test("retained investigation remains browsable after a page reload", async ({ page }) => {
  test.skip(!config.OPERATOR_SECRET, "Configure local authentication first");
  await page.goto("/incidents");
  await page.getByLabel("Local operator secret").fill(config.OPERATOR_SECRET);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("link", { name: "View investigation" }).first().click();
  await expect(page.getByRole("heading", { name: "Source observations" })).toBeVisible({ timeout: 90000 });
  await page.reload();
  await expect(page.getByRole("heading", { name: "Source observations" })).toBeVisible();
});
