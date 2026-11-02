// Domain types = the contract with the modeling team based on the Orchestration Document.
// Aligned with ItemCard v1 and the 6 Objectives (DSO1 to DSO6).

export type Slot = 'top' | 'bottom' | 'onepiece' | 'outer' | 'footwear' | 'bag' | 'accessory';
export type Category = Slot; // Alias for backward compatibility
export type Season = 'spring' | 'summer' | 'autumn' | 'winter' | 'all';
export type Occasion = 'work' | 'casual' | 'evening' | 'sport' | 'ceremony';
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
  features?: Record<string, number>; // variables de contexte de l'Obj6 (renvoyées avec le feedback)
  excludeKey?: string[]; // pièces de la tenue Obj6 (sans accessoires) pour « Autre proposition »
  excludedCount?: number;
}

/** DSO2: Compatibility between candidate item and wardrobe */
export interface CompatibilityResult {
  score: number; // 0–100 (rank100)
  score01?: number; // 0–1
  verdict?: 'compatible' | 'moyenne' | 'peu compatible';
  newOutfits: number;
  partners?: PairScore[];
  duplicate?: {
    id: string;
    similarity: number;
    pct: number;
    is_duplicate: boolean;
  };
  clashingItems: ClothingItem[];
  notes: string[];
  category?: string; // catégorie Obj2 utilisée (tops, bottoms, shoes…)
  guessedCategory?: string; // catégorie devinée sur la photo
  categories?: string[]; // catégories que l'utilisateur peut choisir pour corriger
  pairs?: PairScore[]; // accord avec chaque pièce d'une autre catégorie (/pairs de l'Obj2)
  clashing?: PairScore[]; // pièces à éviter avec elle
  compared?: number; // pièces de la garde-robe comparées
}

export interface PairScore { id: string; pair_score01: number; verdict?: 'va bien' | 'moyen' | 'à éviter' }

/** DSO3: Jury de Tenues (Objectif 3 — TAYSSIR) */
export type JuryVerdict = 'convient' | 'a_ameliorer' | 'deconseille';

export interface OutfitJuryResult {
  score: number; // 0-100
  verdict: JuryVerdict;
  verdictLabel: string;
  rationale: string;
  mode?: 'complet' | 'regles'; // complet = règles + LLM + hybride (DRESSME_JURY_LLM=1 et une clé)
  notes?: string[]; // remarques de l'Obj3 (clé absente, quota LLM atteint…)
  judges: {
    rules: { status: 'pass' | 'warn' | 'fail'; message: string };
    visual: { score01: number | null; status: 'pass' | 'warn' | 'fail' | 'unavailable'; message: string }; // null = non disponible
    llm: { verdict: string; critique: string };
    context: {
      matchWeather: boolean | null; // null = température non fournie
      matchOccasion: boolean;
      weatherLevel?: number | null; // 0 inadapté, 1 à ajuster, 2 adapté (critère météo de l'Obj3)
      occasionLevel?: number; // idem pour la formalité vis-à-vis de l'occasion
      message: string;
    };
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
  rationale?: string; // pourquoi cette pièce (IA de l'Obj4 ou liste de base)
  proxy?: ClothingItem | null; // votre pièce de même catégorie qui sert à simuler la pièce proposée
  proxyColourDiffers?: boolean; // la pièce de simulation n'a pas la couleur demandée
  gain_likely?: number; // nouvelles tenues estimées (associations jugées plus probables qu'improbables)
}

/** DSO4 : analyse des pièces manquantes (GET /gaps) */
export interface GapAnalysis {
  mode: 'analyse' | 'exemple'; // exemple = rapport statique (garde-robe sans photos)
  notice?: string;
  source: 'ia' | 'base' | null; // qui a proposé les pièces : IA ou liste de pièces de base
  model?: string | null;
  pieces?: number;
  pairsScored?: number;
  outfitsNow: { lower: number; upper: number; likely?: number } | null; // tenues possibles aujourd'hui (prudent / optimiste / estimé)
  shoppingEnabled?: boolean; // recherche de boutiques configurée sur le serveur
  calibrated?: boolean;
  gaps: GapSuggestion[];
  unscorable: { description: string; slot: Slot; rationale: string }[]; // pas de pièce de cette catégorie pour simuler
}

export interface ShopOption {
  title: string;
  url: string;
  site: string; // nom de domaine du vendeur
  description: string; // description de la page produit (sinon extrait de la recherche)
  price: number | null;
  currency: string | null;
  priceTnd?: number | null; // prix converti en dinars (taux approximatif) pour comparer les devises
  imageUrl?: string | null;
  product: boolean; // fiche produit (prix ou balises produit) plutôt qu'un article
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
  palette?: { color: string; weight: number; pieces?: number }[]; // pieces = nombre de pièces de cette couleur
  model?: 'garde-robe' | 'référence'; // référence = taxonomie de styles apprise sur le catalogue de l'Obj5
  nStyles?: number; // nombre de styles de cette taxonomie
  dominantPieces?: { id: string; name?: string }[]; // vos pièces rangées dans le style dominant
  persona?: StyleAxis; // orientation calculée par l'Obj5
  dominantShare?: number | null; // part de la garde-robe dans le style dominant (0-100)
  pricePercentile?: number | null; // 0-100, null = prix inconnus
  slotCounts?: Partial<Record<Slot, number>>;
  nItems?: number;
  nItemsUsed?: number;
  space?: 'photos' | 'attributs'; // photos = FashionCLIP, attributs = repli sur les champs des fiches
  notes?: string[];
}

/** DSO5 : pièce du catalogue de référence qui prolonge votre style */
export interface StyleSuggestion {
  id: string;
  name?: string;
  slot: Slot;
  type?: string;
  colour: string[];
  usage?: string;
  formality?: number;
  match: number; // score de classement : proximité avec la garde-robe + bonus de l'orientation (0-100)
  reasons: string[];
}

/** DSO6 : écran « tenue du jour » complet (POST /outfits/recommend) */
export type Gender = 'Women' | 'Men';

export interface RecommendRequest {
  gender?: Gender;
  city: string;
  agenda?: string; // texte libre (français, arabe ou anglais) lu par l'agent de l'Obj6
  colours: string[]; // envies facultatives : rien = aucun filtre
  types: string[];
  explain: boolean; // explications rédigées par la styliste IA
  k?: number;
  exclude_outfits?: string[][];
}

export interface RecommendedOutfit {
  id: string;
  items: ClothingItem[];
  accessories: ClothingItem[];
  score: number; // 0 à 1 (contexte, météo, envies, historique)
  compat01: number | null; // accord entre les pièces (Obj2)
  jury: string; // verdict du jury de style (Obj3)
  reasons: string[]; // raisons calculées
  explanation?: string | null; // explication de la styliste IA
  alerts: string[]; // points faibles
  excludeKey: string[];
  features: Record<string, number>;
}

export interface RecommendResponse {
  context: {
    city: string;
    temperatureC: number;
    rainPct: number;
    occasion: string;
    formality: number | null;
    agent: string | null; // qui a lu l'agenda : mots-clés, IA, IA + fiches locales
    rag: string[]; // fiches locales consultées
    ramadan: boolean;
    eid: boolean;
    notes?: string | null;
    pieces: number;
  };
  warnings: string[];
  message: string | null;
  steps: { label: string; ms: number }[];
  outfits: RecommendedOutfit[];
}

export interface OutfitOptions {
  colours: string[];
  types: string[];
  cities: string[];
}
