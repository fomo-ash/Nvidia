const base = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
export async function api<T>(path: string): Promise<T> {
  const response = await fetch(`${base}${path}`);
  if (!response.ok) throw new Error(`API request failed (${response.status})`);
  return response.json() as Promise<T>;
}
