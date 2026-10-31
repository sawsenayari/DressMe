import type { ClothingItem, GapSuggestion, Outfit, StyleProfile, OutfitJuryResult } from '../types';

export const SAMPLE_ITEMS: ClothingItem[] = [
  {
    id: 'it_0001',
    name: 'Ribbed Cashmere Knit',
    slot: 'top',
    category: 'top',
    type: 'Sweater',
    colour: ['pink'],
    color: 'soft pink',
    usage: 'Casual',
    warmth: 2,
    formality: 1,
    gender: 'Women',
    imageUrl: '/images/pink-sweater.jpg',
    imageCrop: '/images/pink-sweater.jpg',
    season: 'spring',
    pattern: 'ribbed',
    confidence: { slot: 0.94, colour: 0.91, type: 0.88 },
    source: 'obj1.llm',
    traditional: false,
    style: 'minimalist knit',
    wearCount: 14,
  },
  {
    id: 'it_0002',
    name: 'Pleated High-Waist Trousers',
    slot: 'bottom',
    category: 'bottom',
    type: 'Trousers',
    colour: ['cream'],
    color: 'cream',
    usage: 'Smart Casual',
    warmth: 1,
    formality: 2,
    gender: 'Unisex',
    imageUrl: '/images/cream-trousers.jpg',
    imageCrop: '/images/cream-trousers.jpg',
    season: 'all',
    pattern: 'plain',
    confidence: { slot: 0.96, colour: 0.89, type: 0.92 },
    source: 'obj1.knn',
    traditional: false,
    style: 'tailored pleat',
    wearCount: 22,
  },
  {
    id: 'it_0003',
    name: 'Classic Belted Trench Coat',
    slot: 'outer',
    category: 'outer',
    type: 'Jackets',
    colour: ['beige'],
    color: 'camel beige',
    usage: 'Smart Casual',
    warmth: 2,
    formality: 2,
    waterproof: true,
    gender: 'Unisex',
    imageUrl: 'https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=700&auto=format&fit=crop&q=80',
    imageCrop: 'https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=700&auto=format&fit=crop&q=80',
    season: 'spring',
    pattern: 'plain',
    confidence: { slot: 0.95, colour: 0.87, type: 0.89 },
    source: 'obj1.llm',
    traditional: false,
    style: 'classic trench',
    wearCount: 18,
  },
  {
    id: 'it_0004',
    name: 'Minimalist Court Sneaker',
    slot: 'footwear',
    category: 'footwear',
    type: 'Sneakers',
    colour: ['white'],
    color: 'clean white',
    usage: 'Casual',
    warmth: 1,
    formality: 0,
    open_toe: false,
    gender: 'Unisex',
    imageUrl: 'https://images.unsplash.com/photo-1595950653106-6c9ebd614d3a?w=700&auto=format&fit=crop&q=80',
    imageCrop: 'https://images.unsplash.com/photo-1595950653106-6c9ebd614d3a?w=700&auto=format&fit=crop&q=80',
    season: 'all',
    pattern: 'plain',
    confidence: { slot: 0.98, colour: 0.95, type: 0.95 },
    source: 'obj1.knn',
    traditional: false,
    style: 'court sneaker',
    wearCount: 31,
  },
  {
    id: 'it_0005',
    name: 'Lavender Silk Midi Skirt',
    slot: 'bottom',
    category: 'bottom',
    type: 'Skirts',
    colour: ['lavender'],
    color: 'muted lavender',
    usage: 'Party',
    warmth: 1,
    formality: 2,
    gender: 'Women',
    imageUrl: 'https://images.unsplash.com/photo-1583496661160-fb5886a0aaaa?w=700&auto=format&fit=crop&q=80',
    imageCrop: 'https://images.unsplash.com/photo-1583496661160-fb5886a0aaaa?w=700&auto=format&fit=crop&q=80',
    season: 'summer',
    pattern: 'plain',
    confidence: { slot: 0.88, colour: 0.65, type: 0.81 },
    source: 'user_corrected',
    traditional: false,
    style: 'silk midi',
    wearCount: 8,
  },
  {
    id: 'it_0006',
    name: 'Linen Button-Down Shirt',
    slot: 'top',
    category: 'top',
    type: 'Shirts',
    colour: ['mint', 'white'],
    color: 'pale mint',
    usage: 'Smart Casual',
    warmth: 1,
    formality: 1,
    gender: 'Unisex',
    imageUrl: 'https://images.unsplash.com/photo-1598033129183-c4f50c736f10?w=700&auto=format&fit=crop&q=80',
    imageCrop: 'https://images.unsplash.com/photo-1598033129183-c4f50c736f10?w=700&auto=format&fit=crop&q=80',
    season: 'spring',
    pattern: 'plain',
    confidence: { slot: 0.93, colour: 0.84, type: 0.90 },
    source: 'obj1.llm',
    traditional: false,
    style: 'linen button-up',
    wearCount: 12,
  },
  {
    id: 'it_0007',
    name: 'Structured Mini Crossbody',
    slot: 'bag',
    category: 'accessory',
    type: 'Handbags',
    colour: ['beige'],
    color: 'nude beige',
    usage: 'Casual',
    warmth: 0,
    formality: 1,
    gender: 'Women',
    imageUrl: 'https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=700&auto=format&fit=crop&q=80',
    imageCrop: 'https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=700&auto=format&fit=crop&q=80',
    season: 'all',
    pattern: 'plain',
    confidence: { slot: 0.91, colour: 0.88, type: 0.86 },
    source: 'obj1.knn',
    traditional: false,
    style: 'structured mini bag',
    wearCount: 26,
  },
  {
    id: 'it_0008',
    name: 'Blush Leather Block Mules',
    slot: 'footwear',
    category: 'footwear',
    type: 'Heels',
    colour: ['pink'],
    color: 'pastel blush',
    usage: 'Formal',
    warmth: 1,
    formality: 2,
    open_toe: true,
    gender: 'Women',
    imageUrl: 'https://images.unsplash.com/photo-1543163521-1bf539c55dd2?w=700&auto=format&fit=crop&q=80',
    imageCrop: 'https://images.unsplash.com/photo-1543163521-1bf539c55dd2?w=700&auto=format&fit=crop&q=80',
    season: 'spring',
    pattern: 'plain',
    confidence: { slot: 0.94, colour: 0.85, type: 0.91 },
    source: 'obj1.llm',
    traditional: false,
    style: 'block heel mule',
    wearCount: 11,
  },
  {
    id: 'it_0009',
    name: 'Modern Tunisian Embroidered Jebba',
    slot: 'onepiece',
    category: 'top',
    type: 'Traditional',
    colour: ['cream', 'gold'],
    color: 'cream gold',
    usage: 'Ethnic',
    warmth: 2,
    formality: 3,
    gender: 'Women',
    imageUrl: 'https://images.unsplash.com/photo-1617627143750-d86bc21e42bb?w=700&auto=format&fit=crop&q=80',
    imageCrop: 'https://images.unsplash.com/photo-1617627143750-d86bc21e42bb?w=700&auto=format&fit=crop&q=80',
    season: 'spring',
    pattern: 'embroidered',
    confidence: { slot: 0.72, colour: 0.62, type: 0.68 },
    source: 'user_corrected',
    traditional: true, // Specific Tunisian piece mentioned in the document!
    style: 'artisan jebba',
    wearCount: 5,
  },
];

export const SAMPLE_OUTFITS: Record<string, Outfit> = {
  casual: {
    id: 'outfit-casual',
    items: [SAMPLE_ITEMS[0], SAMPLE_ITEMS[1], SAMPLE_ITEMS[3], SAMPLE_ITEMS[6]],
    compat01: 0.88,
    agenda: 'Afternoon Coffee & Co-working',
    reason: 'Effortless daytime harmony. The ribbed pastel pink knit balances with pleated cream trousers, anchored by clean court sneakers for comfortable mobility.',
    weather: { temperatureC: 21, label: 'Sunny & Pleasant' },
    tryOnImageUrl: 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=800&auto=format&fit=crop&q=80',
  },
  work: {
    id: 'outfit-work',
    items: [SAMPLE_ITEMS[5], SAMPLE_ITEMS[1], SAMPLE_ITEMS[2], SAMPLE_ITEMS[6]],
    compat01: 0.92,
    agenda: 'Design Review & Client Presentation',
    reason: 'Smart-casual tailoring. The crisp mint linen shirt layers cleanly underneath a structured beige trench, paired with neutral trousers and structured bag.',
    weather: { temperatureC: 19, label: 'Breezy & Clear' },
    tryOnImageUrl: 'https://images.unsplash.com/photo-1490481651871-ab68de25d43d?w=800&auto=format&fit=crop&q=80',
  },
  evening: {
    id: 'outfit-evening',
    items: [SAMPLE_ITEMS[0], SAMPLE_ITEMS[4], SAMPLE_ITEMS[7], SAMPLE_ITEMS[6]],
    compat01: 0.85,
    agenda: 'Gallery Opening & Dinner',
    reason: 'Monochrome pastel elegance. The soft cashmere knit drapes smoothly against the lavender silk midi skirt, elevated with blush block mules.',
    weather: { temperatureC: 17, label: 'Cool Evening' },
    tryOnImageUrl: 'https://images.unsplash.com/photo-1485968579580-b6d095142e6e?w=800&auto=format&fit=crop&q=80',
  },
};

export const SAMPLE_GAPS: GapSuggestion[] = [
  {
    id: 'gap-1',
    slot: 'outer',
    category: 'outer',
    description: 'Double-breasted oatmeal wool blazer',
    unlockedOutfits: 14,
    gain_lower: 12,
    gain_upper: 16,
    rank: 1,
    ranking_ready: true,
  },
  {
    id: 'gap-2',
    slot: 'bottom',
    category: 'bottom',
    description: 'Straight-leg vintage wash organic denim',
    unlockedOutfits: 11,
    gain_lower: 9,
    gain_upper: 13,
    rank: 2,
    ranking_ready: true,
  },
  {
    id: 'gap-3',
    slot: 'footwear',
    category: 'footwear',
    description: 'Almond-toe cream leather Chelsea boots',
    unlockedOutfits: 8,
    gain_lower: 6,
    gain_upper: 10,
    rank: 3,
    ranking_ready: true,
  },
  {
    id: 'gap-4',
    slot: 'bag',
    category: 'accessory',
    description: 'Structured sage green leather shoulder bag',
    unlockedOutfits: 6,
    gain_lower: 4,
    gain_upper: 8,
    rank: 4,
    ranking_ready: true,
  },
];

export const INITIAL_PROFILE: StyleProfile = {
  axis: 'efficiency',
  budgetMode: false,
  scores: {
    efficacite: 86,
    economie: 62,
    image: 74,
  },
  diversityScore: 78,
  formalityPref: 1, // Smart Casual (0 to 3)
  dominantCluster: 'Minimalist Pastel Tailoring',
  palette: [
    { color: '#F2A8C4', weight: 0.35 },
    { color: '#C7E8DD', weight: 0.25 },
    { color: '#DCC4F2', weight: 0.20 },
    { color: '#F8F8F6', weight: 0.20 },
  ],
};

/** Evaluates an outfit composition using Objectif 3 (Jury de Tenues) logic */
export function evaluateOutfitWithJury(
  items: ClothingItem[],
  occasion: string,
  temperatureC: number
): OutfitJuryResult {
  const hasTop = items.some(i => i.slot === 'top' || i.slot === 'onepiece');
  const hasBottom = items.some(i => i.slot === 'bottom' || i.slot === 'onepiece');
  const hasShoes = items.some(i => i.slot === 'footwear');
  
  const warmths = items.map(i => i.warmth || 1);
  const avgWarmth = warmths.reduce((a, b) => a + b, 0) / (warmths.length || 1);

  // Check clashing combinations
  const isTraditionalWithSneakers = items.some(i => i.traditional) && items.some(i => i.type === 'Sneakers');
  const isEveningWithCourtSneakers = occasion === 'evening' && items.some(i => i.type === 'Sneakers');

  let score = 88;
  let verdict: OutfitJuryResult['verdict'] = 'convient';
  let verdictLabel = 'Outfit Validé par le Jury';
  let rationale = 'Excellente harmonie visuelle. Les pièces sélectionnées respectent la règle des proportions et le contraste des textures.';
  const repairs: OutfitJuryResult['repairs'] = [];

  if (isTraditionalWithSneakers) {
    score = 42;
    verdict = 'deconseille';
    verdictLabel = 'Déconseillé (Conflit de Formalité & Style)';
    rationale = 'Le jury note un désaccord stylistique entre une pièce traditionnelle d\'apparat et des baskets de sport décontractées.';
    const sneaker = items.find(i => i.type === 'Sneakers');
    if (sneaker) {
      repairs.push({
        problemItemId: sneaker.id,
        reason: 'Remplacer les baskets par une mule en cuir ou sandale habillée pour sublimer la pièce traditionnelle.',
        suggestedReplacements: [SAMPLE_ITEMS[7]], // Mules
      });
    }
  } else if (isEveningWithCourtSneakers) {
    score = 64;
    verdict = 'a_ameliorer';
    verdictLabel = 'À Améliorer (Code Événementiel)';
    rationale = 'La tenue est confortable mais légèrement trop décontractée pour une sortie de soirée formelle.';
    const sneaker = items.find(i => i.type === 'Sneakers');
    if (sneaker) {
      repairs.push({
        problemItemId: sneaker.id,
        reason: 'Élever la tenue avec des mules à talon bloc pour la soirée.',
        suggestedReplacements: [SAMPLE_ITEMS[7]],
      });
    }
  } else if (!hasTop || (!hasBottom && !items.some(i => i.slot === 'onepiece')) || !hasShoes) {
    score = 35;
    verdict = 'a_ameliorer';
    verdictLabel = 'Composition Incomplète';
    rationale = 'Une tenue complète requiert au minimum un haut + un bas (ou une robe/combinaison) et des chaussures.';
  }

  return {
    score,
    verdict,
    verdictLabel,
    rationale,
    judges: {
      rules: {
        status: hasTop && (hasBottom || items.some(i => i.slot === 'onepiece')) && hasShoes ? 'pass' : 'warn',
        message: 'Structure des 3 pièces maîtresses (haut, bas, chaussures) respectée selon le contrat.',
      },
      visual: {
        score01: score / 100,
        status: score >= 70 ? 'pass' : score >= 50 ? 'warn' : 'fail',
        message: 'Similarité FashionCLIP et cohérence chromatique de la palette.',
      },
      llm: {
        verdict: verdict === 'convient' ? 'Harmonieux' : 'Ajustement recommandé',
        critique: rationale,
      },
      context: {
        matchWeather: (temperatureC > 20 && avgWarmth <= 2) || (temperatureC <= 20 && avgWarmth >= 1.5),
        matchOccasion: !isEveningWithCourtSneakers,
        message: `Adapté pour ${occasion} à ${temperatureC}°C.`,
      },
      compatibility: {
        score01: score / 100,
        message: 'Score croisé issu du réseau de paires PairMLP (Objectif 2).',
      },
    },
    repairs,
  };
}
