import type { Gender, Occasion, Outfit, OutfitOptions, RecommendRequest, RecommendResponse } from '../types';
import { assetUrl, http } from './http';
import { withAssets } from './wardrobe';

// DSO3 + DSO6 — outfit of the day (weather and calendar handled server-side)
/** agenda : texte libre lu par l'Obj6 ; exclude : tenues déjà écartées (« Autre proposition »). */
export const getOutfitOfDay = (occasion: Occasion, budgetMode: boolean, agenda?: string, exclude: string[][] = []) => {
  const q = new URLSearchParams({ occasion, budget: String(budgetMode) });
  if (agenda) q.set('agenda', agenda);
  if (exclude.length) q.set('exclude', exclude.map(g => g.join(',')).join(';'));
  return http<Outfit>(`/outfits/today?${q}`).then(o => ({ ...o, items: o.items.map(withAssets) }));
};

export type FeedbackReason = 'too_hot' | 'too_cold' | 'too_formal' | 'too_casual' | 'style';

/** Avis sur la tenue, mémorisé par l'Obj6 : 👍 favorise ces pièces et les marque « portées » (rotation des jours suivants). */
export const sendOutfitFeedback = (itemIds: string[], accepted: boolean, features: Record<string, number> = {}, reason?: FeedbackReason) =>
  http<{ stored: boolean; feedback: number; accepted: number }>('/outfits/feedback', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ item_ids: itemIds, accepted, features, reason }),
  });

/** Couleurs et types proposés comme « envies » (présents dans la garde-robe pour ce genre) et villes. */
export const getOutfitOptions = (gender?: Gender) =>
  http<OutfitOptions>(`/outfits/options${gender ? `?gender=${gender}` : ''}`);

/** Tenues du jour : agenda lu par l'IA, météo de la ville, envies, jury de style et accord des pièces. */
export const recommendOutfits = (body: RecommendRequest) =>
  http<RecommendResponse>('/outfits/recommend', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  }).then(r => ({
    ...r,
    outfits: r.outfits.map(o => ({ ...o, items: o.items.map(withAssets), accessories: o.accessories.map(withAssets) })),
  }));

export interface TryOnResult {
  imageUrl: string;
  worn: string[];
  notWorn: string[];
  note: string | null;
  cached: boolean;
}

/** Essayage réaliste : les photos des pièces (haut, bas ou robe) portées par un mannequin photo (≈ 30 s à 2 min). */
export const tryOnOutfit = (itemIds: string[], gender?: Gender) =>
  http<TryOnResult>('/outfits/tryon', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ item_ids: itemIds, gender }),
  }).then(r => ({ ...r, imageUrl: assetUrl(r.imageUrl) ?? r.imageUrl }));

/** Tenue « inspirée » (illimitée) : photos décrites par Gemini, image de mode générée par FLUX à partir de ces descriptions. */
export const inspireOutfit = (itemIds: string[], gender?: Gender) =>
  http<TryOnResult>('/outfits/inspire', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ item_ids: itemIds, gender }),
  }).then(r => ({ ...r, imageUrl: assetUrl(r.imageUrl) ?? r.imageUrl }));
