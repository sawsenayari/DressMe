import { NavLink, Outlet } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import { AuthModal } from '../ui/AuthModal';

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
  bell: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/>
      <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>
    </svg>
  ),
};

const NAV_LINKS = [
  { to: '/', label: 'Today', icon: Icons.today },
  { to: '/wardrobe', label: 'Wardrobe', icon: Icons.wardrobe },
  { to: '/studio', label: 'Outfit Studio', icon: Icons.studio },
  { to: '/match', label: 'Does it match?', icon: Icons.match },
  { to: '/gaps', label: 'Gaps', icon: Icons.gaps },
  { to: '/profile', label: 'Style Profile', icon: Icons.profile },
];

export function AppShell() {
  const { useDemoData, setUseDemoData, searchQuery, setSearchQuery, setIsAuthModalOpen } = useApp();

  return (
    <div className="shell">
      {/* Desktop Sidebar */}
      <aside className="side">
        <div className="brand-wrapper">
          <div className="brand-icon">✨</div>
          <div>
            <div className="brand-title">DressMe</div>
            <div className="brand-subtitle">Styling Studio</div>
          </div>
        </div>

        <nav aria-label="Main Navigation">
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

        {/* Sidebar promotional card inspired by PinHome */}
        <div className="side-promo">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <span style={{ fontSize: '18px' }}>🌸</span>
            <span className="side-promo-title">AI Stylist Pro</span>
          </div>
          <div className="side-promo-desc">
            Get personalized season palettes and smart shopping compatibility.
          </div>
          <button className="side-promo-btn" onClick={() => setIsAuthModalOpen(true)}>
            <span>View Benefits</span>
            <span>→</span>
          </button>
        </div>

        {/* User Profile item at sidebar bottom */}
        <div className="side-user" onClick={() => setIsAuthModalOpen(true)} title="Manage Profile & Account">
          <img
            src="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80"
            alt="Camille Stinson"
            className="user-avatar"
          />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="user-name" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              Camille Stinson
            </div>
            <div className="user-role">Free Member • Pro Mode</div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="content">
        {/* Top bar with search, weather, demo mode toggle, and notification bell */}
        <header className="topbar">
          <div className="topbar-search">
            <span className="topbar-search-icon">{Icons.search}</span>
            <input
              type="text"
              placeholder="Search wardrobe, colors, categories…"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              aria-label="Search wardrobe"
            />
          </div>

          <div className="topbar-actions">
            {/* Live weather badge */}
            <div className="topbar-pill" title="Current weather for outfit styling">
              <span className="pill-dot"></span>
              <span>Paris <strong>21°C</strong> Mild & Sunny</span>
            </div>

            {/* Demo / Live Backend Toggle */}
            <button
              className={`demo-toggle-btn ${useDemoData ? 'active' : 'inactive'}`}
              onClick={() => setUseDemoData(!useDemoData)}
              title={useDemoData ? 'Using rich sample wardrobe. Click to connect to backend endpoints.' : 'Connected to live model API (/api). Click to switch to sample wardrobe.'}
            >
              <span>{useDemoData ? '✨ Sample Wardrobe: ON' : '⚡ Live Model API'}</span>
            </button>

            {/* Notification bell button */}
            <button
              className="topbar-pill"
              style={{ padding: '8px 12px', cursor: 'pointer' }}
              onClick={() => setIsAuthModalOpen(true)}
              aria-label="Notifications"
            >
              {Icons.bell}
            </button>
          </div>
        </header>

        {/* Routed Page */}
        <Outlet />
      </main>

      {/* Mobile Tabbar (<860px) */}
      <nav className="tabbar" aria-label="Mobile Navigation">
        {NAV_LINKS.map(link => (
          <NavLink
            key={link.to}
            to={link.to}
            end={link.to === '/'}
            className={({ isActive }) => (isActive ? 'active' : '')}
          >
            <span className="nav-icon">{link.icon}</span>
            <span>{link.label === 'Style Profile' ? 'Profile' : link.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Global Auth / Onboarding Modal */}
      <AuthModal />
    </div>
  );
}
