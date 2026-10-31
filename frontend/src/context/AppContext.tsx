import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import type { ClothingItem, GapSuggestion, Outfit, Occasion, StyleProfile, CompatibilityResult } from '../types';
import { SAMPLE_ITEMS, SAMPLE_OUTFITS, SAMPLE_GAPS, INITIAL_PROFILE } from '../data/sampleData';

interface AppContextType {
  useDemoData: boolean;
  setUseDemoData: (v: boolean) => void;
  wardrobe: ClothingItem[];
  addWardrobeItem: (item: ClothingItem) => void;
  profile: StyleProfile;
  setProfile: (p: StyleProfile) => void;
  gaps: GapSuggestion[];
  getDemoOutfit: (occasion: Occasion, budget: boolean) => Outfit;
  scoreDemoCandidate: (file: File) => Promise<CompatibilityResult>;
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  isAuthModalOpen: boolean;
  setIsAuthModalOpen: (open: boolean) => void;
}

const AppContext = createContext<AppContextType | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  // Default to true so user immediately sees rich, beautiful fashion visuals,
  // but can toggle off if connecting to live model server
  const [useDemoData, setUseDemoData] = useState<boolean>(() => {
    const saved = localStorage.getItem('dressme_demo_mode');
    return saved !== null ? saved === 'true' : true;
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
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);

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

  const getDemoOutfit = (occasion: Occasion, budget: boolean): Outfit => {
    const base = SAMPLE_OUTFITS[occasion] || SAMPLE_OUTFITS.casual;
    if (budget) {
      return {
        ...base,
        reason: `[Budget Optimized] Re-wearing your top-rated wardrobe staples. ${base.reason}`,
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
        'Complements 80% of your neutral tops and bottoms.',
        'High versatility: transitions from casual to evening effortlessly.',
        'Fabric & palette align with your spring & autumn seasonal profile.',
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
        profile,
        setProfile,
        gaps: SAMPLE_GAPS,
        getDemoOutfit,
        scoreDemoCandidate,
        searchQuery,
        setSearchQuery,
        isAuthModalOpen,
        setIsAuthModalOpen,
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
