import type { CompatibilityResult } from '../types';
import { upload } from './http';

// DSO2 — "Does it match?"
export const scoreCandidate = (photo: File) => upload<CompatibilityResult>('/compatibility/score', photo);
