import { useState } from 'react';
import { useAsync } from '../hooks/useAsync';
import { listGaps } from '../services/gaps';
import type { GapSuggestion } from '../types';
import { DataState } from '../components/ui/DataState';
import { useApp } from '../context/AppContext';

const GAP_IMAGES: Record<string, string> = {
  'gap-1': 'https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=700&auto=format&fit=crop&q=80',
  'gap-2': 'https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=700&auto=format&fit=crop&q=80',
  'gap-3': 'https://images.unsplash.com/photo-1543163521-1bf539c55dd2?w=700&auto=format&fit=crop&q=80',
  'gap-4': 'https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=700&auto=format&fit=crop&q=80',
};

export default function Gaps() {
  const { useDemoData, gaps: demoGaps } = useApp();
  const apiState = useAsync(listGaps);
  const [wishlist, setWishlist] = useState<Record<string, boolean>>({});
  const [toastMessage, setToastMessage] = useState('');

  const activeGaps: GapSuggestion[] = useDemoData ? demoGaps : (apiState.data || []);
  const totalUnlocked = activeGaps.reduce((sum, g) => sum + g.unlockedOutfits, 0);

  const toggleWishlist = (id: string, name: string) => {
    setWishlist(prev => {
      const next = !prev[id];
      setToastMessage(next ? `"${name}" ajouté à votre Wishlist ! ✨` : `Retiré de la Wishlist`);
      setTimeout(() => setToastMessage(''), 2200);
      return { ...prev, [id]: next };
    });
  };

  return (
    <>
      <header className="page-head">
        <div>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            Manques de Garde-Robe (Gaps) <span style={{ fontSize: '1.6rem' }}>🎯</span>
          </h1>
          <p className="page-subtitle">
            Analyse de rentabilité vestimentaire (Objectif 4). Identifie les archétypes manquants générant le plus de tenues croisées via <code>/pairs</code>.
          </p>
        </div>
      </header>

      {toastMessage && (
        <div
          role="status"
          style={{
            position: 'fixed',
            bottom: '24px',
            right: '24px',
            background: 'var(--ink)',
            color: 'var(--paper)',
            padding: '12px 20px',
            borderRadius: '999px',
            boxShadow: 'var(--shadow-hover)',
            fontSize: '0.88rem',
            fontWeight: 600,
            zIndex: 99,
          }}
        >
          {toastMessage}
        </div>
      )}

      {/* Top Banner Card */}
      <section
        className="card card-mint"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '24px',
          alignItems: 'center',
          marginBottom: '32px',
          padding: '28px',
        }}
      >
        <div>
          <span
            style={{
              fontSize: '0.78rem',
              fontWeight: 700,
              textTransform: 'uppercase',
              color: 'var(--pastel-mint-deep)',
              background: '#FFFFFF',
              padding: '4px 12px',
              borderRadius: '999px',
              display: 'inline-block',
              marginBottom: '8px',
            }}
          >
            Optimisation du dressing
          </span>
          <h2 style={{ fontSize: '1.5rem', marginBottom: '8px' }}>
            +{totalUnlocked} Nouvelles Tenues Accessibles
          </h2>
          <p style={{ color: 'var(--ink)', fontSize: '0.92rem', margin: 0, lineHeight: 1.5 }}>
            Ces pièces stratégiques comblent les ponts manquants entre vos hauts et vos bas actuels.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '16px', justifyContent: 'flex-start', flexWrap: 'wrap' }}>
          <div style={{ background: '#FFFFFF', padding: '14px 20px', borderRadius: '18px', textAlign: 'center' }}>
            <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--pastel-mint-deep)' }}>
              {activeGaps.length}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Pièces Clés
            </div>
          </div>

          <div style={{ background: '#FFFFFF', padding: '14px 20px', borderRadius: '18px', textAlign: 'center' }}>
            <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--pastel-pink-deep)' }}>
              ranking_ready
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Statut Modèle
            </div>
          </div>
        </div>
      </section>

      {/* Gaps List with gain bounds [gain_lower, gain_upper] */}
      {useDemoData ? (
        <ul className="rows">
          {activeGaps.map((gap, index) => {
            const imgUrl = GAP_IMAGES[gap.id] || GAP_IMAGES['gap-1'];
            const isWishlisted = !!wishlist[gap.id];

            return (
              <li key={gap.id} className="row">
                <img
                  src={imgUrl}
                  alt={gap.description}
                  className="row-img"
                  style={{
                    width: '84px',
                    height: '100px',
                    borderRadius: '16px',
                    objectFit: 'cover',
                    boxShadow: 'var(--shadow-subtle)',
                  }}
                />

                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                    <span className="chip-tag chip-tag-lavender">
                      {gap.slot || gap.category}
                    </span>
                    <span style={{ fontSize: '0.78rem', color: 'var(--muted)' }}>
                      Rang #{gap.rank || index + 1}
                    </span>
                  </div>

                  <h3 style={{ fontSize: '1.15rem', color: 'var(--ink)' }}>
                    {gap.description}
                  </h3>

                  <p style={{ color: 'var(--muted)', fontSize: '0.85rem', margin: '4px 0 0' }}>
                    Fourchette d'impact : de <strong>+{gap.gain_lower || gap.unlockedOutfits - 2}</strong> à <strong>+{gap.gain_upper || gap.unlockedOutfits + 2}</strong> tenues débloquées selon l'occasion.
                  </p>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '10px' }}>
                  <strong>+{gap.unlockedOutfits} tenues</strong>
                  <button
                    className={`btn-sm ${isWishlisted ? 'btn-mint' : 'btn-secondary'}`}
                    style={{
                      borderRadius: '999px',
                      padding: '6px 14px',
                      fontSize: '0.8rem',
                      fontWeight: 600,
                    }}
                    onClick={() => toggleWishlist(gap.id, gap.description)}
                  >
                    {isWishlisted ? '✓ En Wishlist' : '+ Wishlist'}
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        <DataState
          state={apiState}
          endpoint="GET /gaps"
          isEmpty={d => d.length === 0}
          pending="Les pièces prioritaires apparaîtront ici après calcul par le modèle de gaps."
        >
          {gaps => (
            <ul className="rows">
              {gaps.map((g, i) => (
                <li key={g.id} className="row">
                  <div style={{ width: '84px', height: '100px', borderRadius: '16px', overflow: 'hidden' }}>
                    <img
                      src={GAP_IMAGES[g.id] || GAP_IMAGES['gap-1']}
                      alt={g.description}
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    />
                  </div>
                  <div>
                    <span className="chip-tag chip-tag-lavender" style={{ marginBottom: '6px', display: 'inline-block' }}>
                      {g.slot || g.category}
                    </span>
                    <h3>{g.description}</h3>
                    <p style={{ color: 'var(--muted)', fontSize: '0.85rem', margin: '4px 0 0' }}>
                      +{g.gain_lower ?? g.unlockedOutfits} à +{g.gain_upper ?? g.unlockedOutfits} tenues estimées.
                    </p>
                  </div>
                  <strong>+{g.unlockedOutfits}</strong>
                </li>
              ))}
            </ul>
          )}
        </DataState>
      )}
    </>
  );
}
