import { http } from './http';

/** État des services, affiché dans le menu (GET /health de la passerelle). */
export interface Health {
  ok: boolean;
  items: number; // pièces dans la garde-robe
  items_avec_embedding: number; // pièces analysées (photo comprise par l'IA)
  ia?: boolean; // clé Gemini ou Groq configurée
  shopping?: boolean; // recherche de boutiques configurée
  tenueDuJour?: boolean; // service de tenue du jour (objectif 6) joignable
}

export const getHealth = () => http<Health>('/health');
