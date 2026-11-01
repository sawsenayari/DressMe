import { useState } from 'react';
import { useAsync } from '../hooks/useAsync';
import { listGaps } from '../services/gaps';
import type { GapSuggestion } from '../types';
import { DataState } from '../components/ui/DataState';
import { useApp } from '../context/AppContext';
import { slotLabel } from '../components/ui/ItemFields';

// Rapport de l'Obj4 en anglais (« black dress ») -> français ; un mot inconnu est gardé tel quel
const GAP_WORDS: Record<string, string> = {
  dress: 'robe', blouse: 'chemisier', skirt: 'jupe', flats: 'ballerines', coat: 'manteau', jacket: 'veste', shirt: 'chemise',
  't-shirt': 't-shirt', tshirt: 't-shirt', jeans: 'jean', trousers: 'pantalon', pants: 'pantalon', sneakers: 'baskets',
  shoes: 'chaussures', heels: 'escarpins', boots: 'bottes', bag: 'sac', handbag: 'sac à main', sweater: 'pull', top: 'haut',
  black: 'noir', white: 'blanc', grey: 'gris', gray: 'gris', beige: 'beige', brown: 'marron', blue: 'bleu', navy: 'bleu marine',
  red: 'rouge', pink: 'rose', green: 'vert', yellow: 'jaune', purple: 'violet', orange: 'orange',
};
const FEMININE = new Set(['robe', 'jupe', 'veste', 'chemise']);
const FEM_ADJ: Record<string, string> = { noir: 'noire', blanc: 'blanche', gris: 'grise', vert: 'verte', violet: 'violette', marron: 'marron' };
const describeGap = (d: string) => {
  const words = d.toLowerCase().split(/\s+/).filter(Boolean);
  if (words.length === 2 && GAP_WORDS[words[0]] && GAP_WORDS[words[1]]) {   // « couleur nom » -> « nom couleur »
    const noun = GAP_WORDS[words[1]];
    const adj = GAP_WORDS[words[0]];
    return `${noun} ${FEMININE.has(noun) ? FEM_ADJ[adj] || adj : adj}`;
  }
  return words.map(w => GAP_WORDS[w] || w).join(' ');
};
const SLOT_ICON: Record<string, string> = { top: '👚', bottom: '👖', onepiece: '👗', outer: '🧥', footwear: '👠', bag: '👜', accessory: '🧣' };

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
            Pièces à ajouter <span style={{ fontSize: '1.6rem' }}>🎯</span>
          </h1>
          <p className="page-subtitle">
            Les quelques pièces qui, ajoutées à votre garde-robe, vous permettraient de créer le plus de nouvelles tenues.
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
                      Priorité {gap.rank || index + 1}
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
          pending="Les pièces à ajouter en priorité apparaîtront ici dès que l'analyse de votre garde-robe sera prête."
        >
          {gaps => (
            <ul className="rows">
              {gaps.map((g, i) => (
                <li key={g.id} className="row">
                  <div style={{ width: '84px', height: '100px', borderRadius: '16px', background: 'var(--pastel-lavender-soft)', display: 'grid', placeItems: 'center', fontSize: '34px' }}
                       aria-hidden="true">
                    {SLOT_ICON[g.slot || g.category] || '🛍️'}
                  </div>
                  <div>
                    <span className="chip-tag chip-tag-lavender" style={{ marginBottom: '6px', display: 'inline-block' }}>
                      Priorité {g.rank ?? i + 1} · {slotLabel(g.slot || g.category)}
                    </span>
                    <h3 style={{ textTransform: 'capitalize' }}>{describeGap(g.description)}</h3>
                    <p style={{ color: 'var(--muted)', fontSize: '0.85rem', margin: '4px 0 0' }}>
                      Avec vos pièces actuelles, elle permettrait environ {g.unlockedOutfits} nouvelle(s) tenue(s).
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
