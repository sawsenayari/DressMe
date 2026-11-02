import type { GapAnalysis, ShopOption } from '../types';
import { assetUrl, http } from './http';

// DSO4 — wardrobe gap detection (calculée sur la garde-robe ; refresh = nouvelles propositions de l'IA)
export const getGapAnalysis = (refresh = false) =>
  http<GapAnalysis>(`/gaps${refresh ? '?refresh=true' : ''}`).then(a => ({
    ...a,
    gaps: a.gaps.map(g => (g.proxy ? { ...g, proxy: { ...g.proxy, imageUrl: assetUrl(g.proxy.imageUrl) ?? '' } } : g)),
  }));

/** Où acheter une pièce manquante (recherche web de l'Obj4) ; maxPrice facultatif. */
export const searchShops = (description: string, slot: string, maxPrice?: number) => {
  const q = new URLSearchParams({ description, slot });
  if (maxPrice != null) q.set('max_price', String(maxPrice));
  return http<{ description: string; options: ShopOption[] }>(`/gaps/shopping?${q}`);
};
