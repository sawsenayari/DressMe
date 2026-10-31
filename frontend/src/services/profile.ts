import type { StyleProfile } from '../types';
import { http } from './http';

// DSO5 — user style profile
export const getProfile = () => http<StyleProfile>('/profile');
export const saveProfile = (p: StyleProfile) =>
  http<StyleProfile>('/profile', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(p) });
