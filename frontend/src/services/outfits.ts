import type { Occasion, Outfit } from '../types';
import { http } from './http';
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
