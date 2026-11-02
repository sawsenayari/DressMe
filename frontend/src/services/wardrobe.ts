import type { ClothingItem } from '../types';
import { assetUrl, http, upload } from './http';

export const withAssets = (i: ClothingItem): ClothingItem => ({ ...i, imageUrl: assetUrl(i.imageUrl) ?? '', imageCrop: assetUrl(i.imageCrop) });

/** Champs qu'un utilisateur peut corriger sur une fiche (contrat ItemCard v1). */
export type ItemPatch = Partial<Pick<ClothingItem,
  'name' | 'slot' | 'type' | 'colour' | 'usage' | 'warmth' | 'formality' | 'season' | 'traditional' | 'waterproof' | 'open_toe' | 'price_dt'>>;

// DSO1 — classification + wardrobe storage
export const listItems = () => http<ClothingItem[]>('/wardrobe/items').then(items => items.map(withAssets));
/** Pièce proposée par le découpage (objectif 6) : un vêtement d'une photo portée, ou la photo détourée. */
export interface CropPart { part: string; label: string; slot: string | null; image: string }   // image : data URL JPEG
export interface CropResult { needed: boolean; kind: 'portée' | 'à plat' | 'propre'; parts: CropPart[] }

/** Améliore la photo avant l'ajout ; needed = false quand elle est déjà propre (fond clair et uni). */
export const cropPhoto = (photo: File) => upload<CropResult>('/wardrobe/crop', photo);

/** Backend classifies the photo (category, color, season, style) and stores the item.
 *  crop : pièce choisie après cropPhoto (analysée telle quelle ; la photo d'origine est gardée). */
export const addItem = (photo: File, crop?: { image: Blob; slot?: string | null }) => {
  if (!crop) return upload<ClothingItem>('/wardrobe/items', photo).then(withAssets);
  const body = new FormData();
  body.append('image', photo);
  body.append('crop', crop.image, 'piece.jpg');
  if (crop.slot) body.append('slot_hint', crop.slot);
  return http<ClothingItem>('/wardrobe/items', { method: 'POST', body }).then(withAssets);
};
/** Correction par l'utilisateur (source = user_corrected). Un patch vide confirme les attributs détectés. */
export const updateItem = (id: string, patch: ItemPatch) =>
  http<ClothingItem>(`/wardrobe/items/${encodeURIComponent(id)}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(patch),
  }).then(withAssets);
/** Supprime la pièce et ses fichiers (photo, découpe, embedding). */
export const deleteItem = (id: string) =>
  http<{ deleted: string; items: number }>(`/wardrobe/items/${encodeURIComponent(id)}`, { method: 'DELETE' });
