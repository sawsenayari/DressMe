import type { GapSuggestion } from '../types';
import { http } from './http';

// DSO4 — wardrobe gap detection
export const listGaps = () => http<GapSuggestion[]>('/gaps');
