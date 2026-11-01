import type { Gender, Slot, StyleAxis, StyleProfile, StyleSuggestion } from '../types';
import { http } from './http';

// DSO5 — user style profile
export const getProfile = () => http<StyleProfile>('/profile');

/** Pièces du catalogue de référence qui prolongent votre style, classées selon votre orientation. */
export const getStyleSuggestions = (slot?: Slot, gender?: Gender, k = 8) => {
  const q = new URLSearchParams({ k: String(k) });
  if (slot) q.set('slot', slot);
  if (gender) q.set('gender', gender);
  return http<{ axis: StyleAxis; gender: Gender | null; items: StyleSuggestion[] }>(`/profile/recommendations?${q}`);
};
