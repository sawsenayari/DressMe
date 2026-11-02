import { http } from './http';

/** Compte connecté (la session est un cookie HttpOnly posé par la passerelle, jamais lisible par le front). */
export interface User {
  id: string;
  name: string;
  email: string;
  authDisabled?: boolean; // passerelle lancée sans comptes (DRESSME_AUTH=0)
}

const json = (body: unknown) => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

export const getMe = () => http<User>('/auth/me');
export const login = (email: string, password: string) => http<User>('/auth/login', json({ email, password }));
export const register = (name: string, email: string, password: string) =>
  http<User>('/auth/register', json({ name, email, password }));
export const logout = () => http<{ ok: boolean }>('/auth/logout', { method: 'POST' });
