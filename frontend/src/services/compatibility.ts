import type { CompatibilityResult } from '../types';
import { http, upload } from './http';

// DSO2 — "Does it match?" ; category : type de pièce corrigé par l'utilisateur (sinon deviné sur la photo)
export const scoreCandidate = (photo: File, category?: string) => {
  if (!category) return upload<CompatibilityResult>('/compatibility/score', photo);
  const body = new FormData();
  body.append('image', photo);
  body.append('category', category);
  return http<CompatibilityResult>('/compatibility/score', { method: 'POST', body });
};
