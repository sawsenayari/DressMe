import type { ClothingItem } from '../types';
import { assetUrl, http, upload } from './http';

export const withAssets = (i: ClothingItem): ClothingItem => ({ ...i, imageUrl: assetUrl(i.imageUrl) ?? '', imageCrop: assetUrl(i.imageCrop) });

/** Champs qu'un utilisateur peut corriger sur une fiche (contrat ItemCard v1). */
export type ItemPatch = Partial<Pick<ClothingItem,
  'name' | 'slot' | 'type' | 'colour' | 'usage' | 'warmth' | 'formality' | 'season' | 'traditional' | 'waterproof' | 'open_toe' | 'price_dt'>>;

// DSO1 — classification + wardrobe storage
export const listItems = () => http<ClothingItem[]>('/wardrobe/items').then(items => items.map(withAssets));
/** Backend classifies the photo (category, color, season, style) and stores the item. */
export const addItem = (photo: File) => upload<ClothingItem>('/wardrobe/items', photo).then(withAssets);
/** Correction par l'utilisateur (source = user_corrected). Un patch vide confirme les attributs détectés. */
export const updateItem = (id: string, patch: ItemPatch) =>
  http<ClothingItem>(`/wardrobe/items/${encodeURIComponent(id)}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(patch),
  }).then(withAssets);
/** Supprime la pièce et ses fichiers (photo, découpe, embedding). */
export const deleteItem = (id: string) =>
  http<{ deleted: string; items: number }>(`/wardrobe/items/${encodeURIComponent(id)}`, { method: 'DELETE' });
