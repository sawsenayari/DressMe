const BASE = import.meta.env.VITE_API_URL ? String(import.meta.env.VITE_API_URL) : '/api';

export async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, init);
  if (!res.ok) {
    // FastAPI renvoie {"detail": "..."} : on le remonte pour l'afficher (501 = objectif pas encore branché).
    const detail = await res.json().then(j => (typeof j?.detail === 'string' ? j.detail : ''), () => '');
    throw new Error(detail ? `${res.status} — ${detail}` : `${res.status} ${path}`);
  }
  return res.json() as Promise<T>;
}

/** Les images servies par le backend ("/files/...") doivent pointer vers lui, pas vers le serveur Vite. */
export const assetUrl = (p?: string | null) => (p && p.startsWith('/') ? BASE + p : p || undefined);

export function upload<T>(path: string, file: File, field = 'image'): Promise<T> {
  const body = new FormData();
  body.append(field, file);
  return http<T>(path, { method: 'POST', body });
}
