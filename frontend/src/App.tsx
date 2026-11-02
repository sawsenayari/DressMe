import { Route, Routes } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell';
import Today from './pages/Today';
import Wardrobe from './pages/Wardrobe';
import DoesItMatch from './pages/DoesItMatch';
import Gaps from './pages/Gaps';
import Profile from './pages/Profile';
import OutfitStudio from './pages/OutfitStudio';
import Auth from './pages/Auth';
import { useApp } from './context/AppContext';

export default function App() {
  const { user, authChecked } = useApp();
  if (!authChecked) {
    return <p role="status" style={{ padding: '40px', textAlign: 'center', color: 'var(--muted)' }}>Chargement…</p>;
  }
  if (!user) return <Auth />;
  // key : changer de compte remonte toutes les pages (aucune donnée du compte précédent ne reste affichée)
  return (
    <Routes key={user.id}>
      <Route element={<AppShell />}>
        <Route index element={<Today />} />
        <Route path="wardrobe" element={<Wardrobe />} />
        <Route path="studio" element={<OutfitStudio />} />
        <Route path="match" element={<DoesItMatch />} />
        <Route path="gaps" element={<Gaps />} />
        <Route path="profile" element={<Profile />} />
      </Route>
    </Routes>
  );
}
