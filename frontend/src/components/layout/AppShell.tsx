import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import { useEffect, useState } from 'react';
import { useAsync } from '../../hooks/useAsync';
import { getWeather, loadCity, weatherLabel } from '../../services/weather';
import { getHealth } from '../../services/health';

// Modern clean SVG icons
const Icons = {
  today: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
      <circle cx="12" cy="12" r="4"/>
    </svg>
  ),
  wardrobe: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z"/>
      <path d="M3 6h18"/>
      <path d="M16 10a4 4 0 0 1-8 0"/>
    </svg>
  ),
  match: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/>
    </svg>
  ),
  studio: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <path d="m10 15 5-3-5-3v6Z"/>
    </svg>
  ),
  gaps: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect width="7" height="7" x="3" y="3" rx="1"/>
      <rect width="7" height="7" x="14" y="3" rx="1"/>
      <rect width="7" height="7" x="14" y="14" rx="1"/>
      <rect width="7" height="7" x="3" y="14" rx="1"/>
    </svg>
  ),
  profile: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="8" r="5"/>
      <path d="M20 21a8 8 0 0 0-16 0"/>
    </svg>
  ),
  search: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8"/>
      <path d="m21 21-4.3-4.3"/>
    </svg>
  ),
};

// short : libellé de la barre d'onglets sur mobile
const NAV_LINKS = [
  { to: '/', label: 'Tenue du jour', short: 'Aujourd\'hui', icon: Icons.today },
  { to: '/wardrobe', label: 'Ma garde-robe', short: 'Garde-robe', icon: Icons.wardrobe },
  { to: '/studio', label: 'Composer une tenue', short: 'Composer', icon: Icons.studio },
  { to: '/match', label: 'Ça va avec ?', short: 'Ça va ?', icon: Icons.match },
  { to: '/gaps', label: 'Pièces à ajouter', short: 'À ajouter', icon: Icons.gaps },
  { to: '/profile', label: 'Mon style', short: 'Mon style', icon: Icons.profile },
];

const dot = (on?: boolean) => (
  <span aria-hidden style={{ width: '8px', height: '8px', borderRadius: '50%', flex: 'none',
                              background: on ? 'var(--pastel-mint-deep)' : 'var(--muted)', opacity: on ? 1 : 0.5 }} />
);

export function AppShell() {
  const { user, logout, searchQuery, setSearchQuery } = useApp();
  const health = useAsync(getHealth, []);
  // météo réelle de la ville choisie dans « Tenue du jour »
  const [city, setCity] = useState(loadCity);
  useEffect(() => {
    const on = (e: Event) => setCity((e as CustomEvent<string>).detail);
    window.addEventListener('dressme-city', on);
    return () => window.removeEventListener('dressme-city', on);
  }, []);
  const wx = useAsync(() => getWeather(city), [city]);
  const navigate = useNavigate();
  const location = useLocation();
  // La recherche porte sur la garde-robe : taper depuis une autre page ouvre Wardrobe avec le filtre
  const onSearch = (q: string) => {
    setSearchQuery(q);
    if (q.trim() && location.pathname !== '/wardrobe') navigate('/wardrobe');
  };

  return (
    <div className="shell">
      {/* Desktop Sidebar */}
      <aside className="side">
        <div className="brand-wrapper">
          <div className="brand-icon">✨</div>
          <div>
            <div className="brand-title">DressMe</div>
            <div className="brand-subtitle">Studio de style</div>
          </div>
        </div>

        <nav aria-label="Navigation principale">
          {NAV_LINKS.map(link => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === '/'}
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            >
              <span className="nav-icon">{link.icon}</span>
              <span>{link.label}</span>
            </NavLink>
          ))}
        </nav>

        {/* État réel des services (GET /health de la passerelle) */}
        <div className="side-promo" aria-label="État des services">
          <div className="side-promo-title" style={{ marginBottom: '8px' }}>État des services</div>
          {health.error ? (
            <div className="side-promo-desc" style={{ color: 'var(--danger)' }}>Serveur injoignable : lancez run_all.bat.</div>
          ) : !health.data ? (
            <div className="side-promo-desc">Vérification…</div>
          ) : (
            <div style={{ display: 'grid', gap: '6px', fontSize: '0.8rem' }}>
              {([
                [true, `${health.data.items} pièce${health.data.items > 1 ? 's' : ''}, ${health.data.items_avec_embedding} analysée${health.data.items_avec_embedding > 1 ? 's' : ''}`],
                [health.data.tenueDuJour, health.data.tenueDuJour ? 'Tenue du jour : disponible' : 'Tenue du jour : service arrêté'],
                [health.data.ia, health.data.ia ? 'IA : activée' : 'IA : sans clé (règles seules)'],
                [health.data.shopping, health.data.shopping ? 'Boutiques en ligne : activées' : 'Boutiques en ligne : non configurées'],
              ] as const).map(([on, text]) => (
                <div key={text} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>{dot(on)}<span>{text}</span></div>
              ))}
            </div>
          )}
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="content">
        {/* Bandeau : recherche, météo, compte connecté */}
        <header className="topbar">
          <div className="topbar-search">
            <span className="topbar-search-icon">{Icons.search}</span>
            <input
              type="text"
              placeholder="Rechercher : nom, couleur, type, saison…"
              value={searchQuery}
              onChange={e => onSearch(e.target.value)}
              onKeyDown={e => { if (e.key === 'Escape') setSearchQuery(''); }}
              aria-label="Rechercher dans la garde-robe"
            />
          </div>

          <div className="topbar-actions">
            {/* Live weather badge */}
            <div className="topbar-pill" title="Météo du jour (ville choisie dans « Tenue du jour »)">
              <span className="pill-dot"></span>
              <span>{city} <strong>· {weatherLabel(wx.data)}</strong></span>
            </div>

            {/* Compte connecté */}
            {user && !user.authDisabled && (
              <button className="topbar-pill" style={{ cursor: 'pointer' }} onClick={logout} title={`Connecté : ${user.email}`}>
                <span aria-hidden>👤</span><span>{user.name}</span><strong>· Se déconnecter</strong>
              </button>
            )}
          </div>
        </header>

        {/* Routed Page */}
        <Outlet />
      </main>

      {/* Mobile Tabbar (<860px) */}
      <nav className="tabbar" aria-label="Navigation mobile">
        {NAV_LINKS.map(link => (
          <NavLink
            key={link.to}
            to={link.to}
            end={link.to === '/'}
            className={({ isActive }) => (isActive ? 'active' : '')}
          >
            <span className="nav-icon">{link.icon}</span>
            <span>{link.short}</span>
          </NavLink>
        ))}
      </nav>

    </div>
  );
}
