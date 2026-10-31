import type { ClothingItem } from '../types';
import { http, upload } from './http';

// DSO1 — classification + wardrobe storage
export const listItems = () => http<ClothingItem[]>('/wardrobe/items');
/** Backend classifies the photo (category, color, season, style) and stores the item. */
export const addItem = (photo: File) => upload<ClothingItem>('/wardrobe/items', photo);
