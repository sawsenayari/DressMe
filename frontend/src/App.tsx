import { Route, Routes } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell';
import Today from './pages/Today';
import Wardrobe from './pages/Wardrobe';
import DoesItMatch from './pages/DoesItMatch';
import Gaps from './pages/Gaps';
import Profile from './pages/Profile';
import OutfitStudio from './pages/OutfitStudio';

export default function App() {
  return (
    <Routes>
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
