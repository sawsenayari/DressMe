const BASE = import.meta.env.VITE_API_URL ? String(import.meta.env.VITE_API_URL) : '/api';

/** Erreur d'appel au serveur : `message` est lisible par l'utilisateur, `status` sert au code. */
export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

export async function http<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + path, { credentials: 'include', ...init });   // cookie de session du compte
  } catch {
    throw new ApiError('Le serveur ne répond pas. Vérifiez qu\'il est bien lancé, puis réessayez.', 0);
  }
  if (!res.ok) {
    // FastAPI renvoie {"detail": "..."} : messages déjà rédigés pour l'utilisateur par la passerelle
    const detail = await res.json().then(j => (typeof j?.detail === 'string' ? j.detail : ''), () => '');
    if (res.status === 401 && !path.startsWith('/auth/'))   // session expirée : l'application revient à la connexion
      window.dispatchEvent(new Event('dressme-unauthorized'));
    if (res.status === 404 && (!detail || detail === 'Not Found'))   // route absente : serveur lancé avant une mise à jour
      throw new ApiError('Le serveur lancé est une ancienne version : fermez-le puis relancez run_all.bat.', 404);
    throw new ApiError(detail || 'Une erreur est survenue. Réessayez dans un instant.', res.status);
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
