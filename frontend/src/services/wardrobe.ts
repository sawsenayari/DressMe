import type { ClothingItem } from '../types';
import { assetUrl, http, upload } from './http';

const withAssets = (i: ClothingItem): ClothingItem => ({ ...i, imageUrl: assetUrl(i.imageUrl) ?? '', imageCrop: assetUrl(i.imageCrop) });

// DSO1 — classification + wardrobe storage
export const listItems = () => http<ClothingItem[]>('/wardrobe/items').then(items => items.map(withAssets));
/** Backend classifies the photo (category, color, season, style) and stores the item. */
export const addItem = (photo: File) => upload<ClothingItem>('/wardrobe/items', photo).then(withAssets);
