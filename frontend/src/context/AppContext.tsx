import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { StyleProfile } from '../types';
import { getMe, logout as apiLogout, type User } from '../services/auth';

interface AppContextType {
  user: User | null; // compte connecté (null : écran de connexion)
  authChecked: boolean; // la session a été vérifiée auprès de la passerelle
  setUser: (u: User | null) => void;
  logout: () => Promise<void>;
  profile: StyleProfile;
  setProfile: (p: StyleProfile) => void;
  searchQuery: string;
  setSearchQuery: (q: string) => void;
}

const AppContext = createContext<AppContextType | null>(null);
const EMPTY_PROFILE: StyleProfile = { axis: 'mixte', budgetMode: false };

export function AppProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [profile, setProfile] = useState<StyleProfile>(EMPTY_PROFILE);
  const [searchQuery, setSearchQuery] = useState('');

  // session existante (cookie) ?
  useEffect(() => {
    getMe().then(setUser).catch(() => setUser(null)).finally(() => setAuthChecked(true));
  }, []);
  // session expirée pendant l'utilisation : retour à l'écran de connexion
  useEffect(() => {
    const off = () => setUser(null);
    window.addEventListener('dressme-unauthorized', off);
    return () => window.removeEventListener('dressme-unauthorized', off);
  }, []);
  // les données d'un compte ne restent pas affichées pour le suivant
  useEffect(() => { setProfile(EMPTY_PROFILE); setSearchQuery(''); }, [user?.id]);

  const logout = async () => {
    try { await apiLogout(); } catch { /* déjà déconnecté */ }
    setUser(null);
  };

  return (
    <AppContext.Provider value={{ user, authChecked, setUser, logout, profile, setProfile, searchQuery, setSearchQuery }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp doit être utilisé dans AppProvider');
  return ctx;
}
