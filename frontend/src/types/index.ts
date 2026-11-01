// Domain types = the contract with the modeling team based on the Orchestration Document.
// Aligned with ItemCard v1 and the 6 Objectives (DSO1 to DSO6).

export type Slot = 'top' | 'bottom' | 'onepiece' | 'outer' | 'footwear' | 'bag' | 'accessory';
export type Category = Slot; // Alias for backward compatibility
export type Season = 'spring' | 'summer' | 'autumn' | 'winter' | 'all';
export type Occasion = 'work' | 'casual' | 'evening';
export type UsageType = 'Casual' | 'Smart Casual' | 'Formal' | 'Sports' | 'Ethnic' | 'Party';
export type StyleAxis = 'efficiency' | 'economy' | 'brand' | 'mixte';

/** DSO1 & Objectif 6: ItemCard v1 common contract */
export interface ClothingItem {
  id: string;
  name?: string;
  slot: Slot;
  category: Slot; // mirrored for backward compatibility
  type?: string; // fine type e.g. "Jackets", "Sweater"
  colour: string[]; // up to 2 colors
  color: string; // primary color string for UI convenience
  usage?: UsageType;
  warmth?: number; // 0 to 4
  formality?: number; // 0 to 3
  waterproof?: boolean;
  open_toe?: boolean;
  gender?: 'Unisex' | 'Women' | 'Men';
  imageUrl: string; // raw photo
  imageCrop?: string; // 512px cutout on clean background (Niveau 1 mannequin)
  season: Season;
  pattern?: string;
  confidence?: {
    slot: number;
    colour: number;
    type: number;
  };
  source?: 'obj1.llm' | 'obj1.knn' | 'user_corrected';
  price_dt?: number | null;
  traditional?: boolean; // Tunisian heritage piece flag (jebba, fouta, etc.)
  style?: string;
  wearCount?: number;
}

/** DSO3 / DSO6: Outfit suggestion */
export interface Outfit {
  id: string;
  items: ClothingItem[];
  compat01?: number | null; // 0 to 1 calculated by Objectif 2 (null = embeddings manquants)
  reason?: string;
  weather?: { temperatureC: number; label: string };
  agenda?: string; // Objectif 6 context variable
  warnings?: string[];
  tryOnImageUrl?: string; // Niveau 2 photorealistic try-on
}

/** DSO2: Compatibility between candidate item and wardrobe */
export interface CompatibilityResult {
  score: number; // 0–100 (rank100)
  score01?: number; // 0–1
  verdict?: 'compatible' | 'moyenne' | 'peu compatible';
  newOutfits: number;
  partners?: { id: string; pair_score01: number }[];
  duplicate?: {
    id: string;
    similarity: number;
    pct: number;
    is_duplicate: boolean;
  };
  clashingItems: ClothingItem[];
  notes: string[];
}

/** DSO3: Jury de Tenues (Objectif 3 — TAYSSIR) */
export type JuryVerdict = 'convient' | 'a_ameliorer' | 'deconseille';

export interface OutfitJuryResult {
  score: number; // 0-100
  verdict: JuryVerdict;
  verdictLabel: string;
  rationale: string;
  judges: {
    rules: { status: 'pass' | 'warn' | 'fail'; message: string };
    visual: { score01: number | null; status: 'pass' | 'warn' | 'fail' | 'unavailable'; message: string }; // null = non disponible
    llm: { verdict: string; critique: string };
    context: { matchWeather: boolean | null; matchOccasion: boolean; message: string }; // null = température non fournie
    compatibility: { score01?: number; message: string }; // absent = non calculable (Obj2)
  };
  repairs: {
    problemItemId: string | null; // null = ajouter une pièce ; suggestedReplacements vide = retirer problemItemId
    reason: string;
    suggestedReplacements: ClothingItem[];
  }[];
}

/** DSO4: Wardrobe Gaps */
export interface GapSuggestion {
  id: string;
  slot: Slot;
  category: Slot;
  description: string;
  unlockedOutfits: number;
  gain_lower?: number;
  gain_upper?: number;
  rank?: number;
  ranking_ready?: boolean;
}

/** DSO5: Style Profile (Ahmed Ayari) */
export interface StyleProfile {
  axis: StyleAxis;
  budgetMode: boolean;
  scores?: {
    efficacite: number | null; // 0-100, null = non calculable
    economie: number | null; // 0-100, null = non calculable
    image: number | null; // 0-100, null = non calculable
  };
  diversityScore?: number; // 0-100 wardrobe variety index
  formalityPref?: number; // 0 to 3
  dominantCluster?: string;
  palette?: { color: string; weight: number }[];
  model?: 'garde-robe' | 'référence'; // référence = moins de 18 pièces : modèle Obj5 pré-entraîné
}
