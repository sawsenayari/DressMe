import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import type { ClothingItem, GapSuggestion, Outfit, Occasion, StyleProfile, CompatibilityResult } from '../types';
import { SAMPLE_ITEMS, SAMPLE_OUTFITS, SAMPLE_GAPS, INITIAL_PROFILE } from '../data/sampleData';

interface AppContextType {
  useDemoData: boolean;
  setUseDemoData: (v: boolean) => void;
  wardrobe: ClothingItem[];
  addWardrobeItem: (item: ClothingItem) => void;
  updateWardrobeItem: (id: string, patch: Partial<ClothingItem>) => void;
  removeWardrobeItem: (id: string) => void;
  profile: StyleProfile;
  setProfile: (p: StyleProfile) => void;
  gaps: GapSuggestion[];
  getDemoOutfit: (occasion: Occasion, budget: boolean) => Outfit;
  scoreDemoCandidate: (file: File) => Promise<CompatibilityResult>;
  searchQuery: string;
  setSearchQuery: (q: string) => void;
}

const AppContext = createContext<AppContextType | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  // Default to true so user immediately sees rich, beautiful fashion visuals,
  // but can toggle off if connecting to live model server
  const [useDemoData, setUseDemoData] = useState<boolean>(() => {
    const saved = localStorage.getItem('dressme_demo_mode');
    return saved === 'true';   // par défaut : la vraie garde-robe (la démo s'active avec le bouton du haut)
  });

  const [wardrobe, setWardrobe] = useState<ClothingItem[]>(() => {
    const saved = localStorage.getItem('dressme_wardrobe');
    return saved ? JSON.parse(saved) : SAMPLE_ITEMS;
  });

  const [profile, setProfileState] = useState<StyleProfile>(() => {
    const saved = localStorage.getItem('dressme_profile');
    return saved ? JSON.parse(saved) : INITIAL_PROFILE;
  });

  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    localStorage.setItem('dressme_demo_mode', String(useDemoData));
  }, [useDemoData]);

  useEffect(() => {
    localStorage.setItem('dressme_wardrobe', JSON.stringify(wardrobe));
  }, [wardrobe]);

  useEffect(() => {
    localStorage.setItem('dressme_profile', JSON.stringify(profile));
  }, [profile]);

  const setProfile = (p: StyleProfile) => {
    setProfileState(p);
  };

  const addWardrobeItem = (item: ClothingItem) => {
    setWardrobe(prev => [item, ...prev]);
  };

  // Mode démo : modifications locales (le mode API passe par PUT / DELETE /wardrobe/items/{id})
  const updateWardrobeItem = (id: string, patch: Partial<ClothingItem>) => {
    setWardrobe(prev => prev.map(i => (i.id === id ? { ...i, ...patch, source: 'user_corrected' } : i)));
  };

  const removeWardrobeItem = (id: string) => {
    setWardrobe(prev => prev.filter(i => i.id !== id));
  };

  const getDemoOutfit = (occasion: Occasion, budget: boolean): Outfit => {
    const base = SAMPLE_OUTFITS[occasion] || SAMPLE_OUTFITS.casual;
    if (budget) {
      return {
        ...base,
        reason: `[Budget] On reporte vos pièces préférées. ${base.reason}`,
      };
    }
    return base;
  };

  const scoreDemoCandidate = async (_file: File): Promise<CompatibilityResult> => {
    await new Promise(r => setTimeout(r, 650));
    return {
      score: 92,
      newOutfits: 7,
      clashingItems: wardrobe.slice(4, 5),
      notes: [
        'S\'accorde avec 80 % de vos hauts et bas neutres.',
        'Très polyvalente : se porte en journée comme en soirée.',
        'Matière et couleurs adaptées au printemps et à l\'automne.',
      ],
    };
  };

  return (
    <AppContext.Provider
      value={{
        useDemoData,
        setUseDemoData,
        wardrobe,
        addWardrobeItem,
        updateWardrobeItem,
        removeWardrobeItem,
        profile,
        setProfile,
        gaps: SAMPLE_GAPS,
        getDemoOutfit,
        scoreDemoCandidate,
        searchQuery,
        setSearchQuery,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used within AppProvider');
  return ctx;
}
