import type { Occasion, OutfitJuryResult } from '../types';
import { http } from './http';
import { withAssets } from './wardrobe';

export interface JudgeOutfitRequest {
  item_ids: string[];
  occasion: Occasion;
  temperatureC?: number;
  rain?: boolean;
}

// DSO3 + DSO2 — jury d'une tenue composée (règles Obj3, compatibilité Obj2)
export const judgeOutfit = (req: JudgeOutfitRequest) =>
  http<OutfitJuryResult>('/outfits/judge', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  }).then(r => ({
    ...r,
    repairs: r.repairs.map(rep => ({ ...rep, suggestedReplacements: rep.suggestedReplacements.map(withAssets) })),
  }));
