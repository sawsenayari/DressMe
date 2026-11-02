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

export interface CompatAdvice { observation: string | null; conseil: string; tenue: string[]; aEviter: string | null }

/** Conseil de la styliste IA (sur demande) : le score reste celui du modèle ; Gemini voit la photo et l'explique. */
export const adviseCandidate = (photo: File, category?: string) => {
  const body = new FormData();
  body.append('image', photo);
  if (category) body.append('category', category);
  return http<CompatibilityResult & { advice: CompatAdvice | null; adviceNote: string | null }>('/compatibility/advice', { method: 'POST', body });
};
