const BASE = import.meta.env.VITE_API_URL ? String(import.meta.env.VITE_API_URL) : '/api';

export async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, init);
  if (!res.ok) throw new Error(`${res.status} ${path}`);
  return res.json() as Promise<T>;
}

export function upload<T>(path: string, file: File, field = 'image'): Promise<T> {
  const body = new FormData();
  body.append(field, file);
  return http<T>(path, { method: 'POST', body });
}
