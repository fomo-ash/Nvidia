import type { paths } from "./schema";

const base = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
type GetPath = {
  [P in keyof paths]: paths[P] extends { get: object } ? P : never;
}[keyof paths];
type GetResponse<P extends GetPath> = paths[P] extends {
  get: { responses: { 200: { content: { "application/json": infer T } } } };
} ? T : never;

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

export async function api<P extends GetPath>(
  path: P,
  options: { signal?: AbortSignal } = {},
): Promise<GetResponse<P>> {
  const response = await fetch(`${base}${path}`, { signal: options.signal });
  if (!response.ok) {
    let message = `API request failed (${response.status})`;
    try {
      const body: unknown = await response.json();
      if (typeof body === "object" && body !== null && "detail" in body && typeof body.detail === "string") {
        message = body.detail;
      }
    } catch {
      // Proxies can return HTML errors instead of the API error shape.
    }
    throw new ApiError(response.status, message);
  }
  return response.json() as Promise<GetResponse<P>>;
}
