import { afterEach, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";

afterEach(() => vi.unstubAllGlobals());

it("preserves API error status and detail", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: false, status: 409, json: async () => ({ detail: "Proposal expired" }),
  }));
  await expect(api("/api/v1/incidents")).rejects.toMatchObject({ status: 409, message: "Proposal expired" });
});

it("handles non-JSON gateway errors", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: false, status: 502, json: async () => { throw new Error("HTML"); },
  }));
  await expect(api("/api/v1/incidents")).rejects.toBeInstanceOf(ApiError);
});

it("forwards cancellation to fetch", async () => {
  const controller = new AbortController();
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
  vi.stubGlobal("fetch", fetch);
  await api("/api/v1/incidents", { signal: controller.signal });
  expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/api/v1/incidents"), { signal: controller.signal });
});
