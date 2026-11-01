import type { Occasion, Outfit } from '../types';
import { http } from './http';
import { withAssets } from './wardrobe';

// DSO3 + DSO6 — outfit of the day (weather and calendar handled server-side)
export const getOutfitOfDay = (occasion: Occasion, budgetMode: boolean) =>
  http<Outfit>(`/outfits/today?occasion=${occasion}&budget=${budgetMode}`).then(o => ({ ...o, items: o.items.map(withAssets) }));
