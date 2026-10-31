import { useState } from 'react';
import { useAsync } from '../hooks/useAsync';
import { getOutfitOfDay } from '../services/outfits';
import type { Occasion, ClothingItem } from '../types';
import { DataState } from '../components/ui/DataState';
import { ItemTile } from '../components/ui/ItemTile';
import { ItemDetailModal } from '../components/ui/ItemDetailModal';
import { MannequinView } from '../components/ui/MannequinView';
import { useApp } from '../context/AppContext';

const OCCASIONS: Occasion[] = ['work', 'casual', 'evening'];

const AGENDAS = [
  '☕ Co-working & Rendez-vous informel',
  '💼 Réunion Client & Présentation Projet',
  '🎨 Vernissage & Dîner en Ville',
  '🌿 Balade Décontractée & Marché',
];

export default function Today() {
  const { useDemoData, getDemoOutfit, wardrobe, profile } = useApp();
  const [occasion, setOccasion] = useState<Occasion>('casual');
  const [selectedAgenda, setSelectedAgenda] = useState(AGENDAS[0]);
  const [budget, setBudget] = useState(false);
  const [feedbackState, setFeedbackState] = useState<'idle' | 'accepted' | 'rejected'>('idle');
  const [selectedItem, setSelectedItem] = useState<ClothingItem | null>(null);
  const [displayMode, setDisplayMode] = useState<'grid' | 'mannequin'>('grid');

  // Live model backend query
  const apiState = useAsync(() => getOutfitOfDay(occasion, budget), [occasion, budget]);

  // Demo outfit fallback
  const demoOutfit = getDemoOutfit(occasion, budget);
  const activeOutfit = useDemoData ? demoOutfit : apiState.data;

  const handleAcceptOutfit = () => {
    setFeedbackState('accepted');
    setTimeout(() => setFeedbackState('idle'), 2500);
  };

  const handleRejectOutfit = () => {
    setFeedbackState('rejected');
    setTimeout(() => setFeedbackState('idle'), 2500);
  };

  return (
    <>
      {/* Welcome Greeting & Contextual Agenda Selector (Objectif 6) */}
      <section style={{ marginBottom: '28px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <h1 style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              Bonjour, Camille <span style={{ fontSize: '1.8rem' }}>✨</span>
            </h1>
            <p className="page-subtitle">
              Recommandation contextuelle basée sur 24 variables : météo, agenda, et profil de style.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <button
              className={`btn-sm ${feedbackState === 'accepted' ? 'btn-mint' : 'btn-secondary'}`}
              style={{ borderRadius: '999px', fontWeight: 600 }}
              onClick={handleAcceptOutfit}
            >
              {feedbackState === 'accepted' ? '✓ Portée Aujourd\'hui !' : '✨ Valider & Porter'}
            </button>
            <button
              className="btn-secondary btn-sm"
              style={{ borderRadius: '999px', fontSize: '0.8rem' }}
              onClick={handleRejectOutfit}
            >
              {feedbackState === 'rejected' ? 'Noté pour l\'IA' : '↻ Autre proposition'}
            </button>
          </div>
        </div>

        {/* Agenda / Event Dropdown (Objectif 6 - Contexte) */}
        <div
          style={{
            marginTop: '16px',
            background: 'var(--surface)',
            padding: '12px 18px',
            borderRadius: '18px',
            border: '1px solid var(--line)',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            flexWrap: 'wrap',
          }}
        >
          <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--ink)' }}>
            📅 Contexte Agenda du jour :
          </span>
          <select
            value={selectedAgenda}
            onChange={e => setSelectedAgenda(e.target.value)}
            className="form-select"
            style={{ padding: '6px 14px', fontSize: '0.86rem', width: 'auto', flex: 1, minWidth: '220px' }}
          >
            {AGENDAS.map(ag => (
              <option key={ag} value={ag}>
                {ag}
              </option>
            ))}
          </select>
          <span className="chip-tag chip-tag-mint" style={{ fontSize: '0.74rem' }}>
            Objectif 6 Actif
          </span>
        </div>

        {/* 4 Colorful Stats Cards */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '16px',
            marginTop: '20px',
          }}
        >
          <div className="card card-pink" style={{ padding: '18px 20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--pastel-pink-deep)', textTransform: 'uppercase' }}>
                Occasion
              </span>
              <span style={{ fontSize: '18px' }}>👗</span>
            </div>
            <div style={{ fontSize: '1.5rem', fontWeight: 800, marginTop: '8px', color: 'var(--ink)' }}>
              {occasion.toUpperCase()}
            </div>
            <div style={{ fontSize: '0.82rem', color: 'var(--muted)', marginTop: '2px' }}>
              {budget ? '🌿 Budget mode actif' : 'Rotation standard'}
            </div>
          </div>

          <div className="card card-mint" style={{ padding: '18px 20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--pastel-mint-deep)', textTransform: 'uppercase' }}>
                Compatibilité Tenue
              </span>
              <span style={{ fontSize: '18px' }}>⚖️</span>
            </div>
            <div style={{ fontSize: '1.5rem', fontWeight: 800, marginTop: '8px', color: 'var(--ink)' }}>
              92 / 100
            </div>
            <div style={{ fontSize: '0.82rem', color: 'var(--muted)', marginTop: '2px' }}>
              Validée par le jury de tenues
            </div>
          </div>

          <div className="card card-butter" style={{ padding: '18px 20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--pastel-butter-deep)', textTransform: 'uppercase' }}>
                Stratégie de Style
              </span>
              <span style={{ fontSize: '18px' }}>⚡</span>
            </div>
            <div style={{ fontSize: '1.5rem', fontWeight: 800, marginTop: '8px', color: 'var(--ink)', textTransform: 'capitalize' }}>
              {profile.axis}
            </div>
            <div style={{ fontSize: '0.82rem', color: 'var(--muted)', marginTop: '2px' }}>
              {profile.scores?.efficacite || 86}% d'efficacité matin
            </div>
          </div>

          <div className="card card-lavender" style={{ padding: '18px 20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--pastel-lavender-deep)', textTransform: 'uppercase' }}>
                Météo Paris
              </span>
              <span style={{ fontSize: '18px' }}>⛅</span>
            </div>
            <div style={{ fontSize: '1.5rem', fontWeight: 800, marginTop: '8px', color: 'var(--ink)' }}>
              21°C
            </div>
            <div style={{ fontSize: '0.82rem', color: 'var(--muted)', marginTop: '2px' }}>
              Douceur & ciel dégagé
            </div>
          </div>
        </div>
      </section>

      {/* Occasion & Display Mode Switcher (Grid vs Mannequin) */}
      <section style={{ marginBottom: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '14px' }}>
        <div className="chips" role="group" aria-label="Occasion" style={{ marginBottom: 0 }}>
          {OCCASIONS.map(o => (
            <button
              key={o}
              className="chip"
              aria-pressed={o === occasion}
              onClick={() => setOccasion(o)}
            >
              {o === 'work' ? '💼 Travail' : o === 'casual' ? '☕ Casual Chic' : '🌙 Soirée'}
            </button>
          ))}
          <button
            className="chip"
            aria-pressed={budget}
            onClick={() => setBudget(b => !b)}
            title="Priorise les basiques déjà bien rentabilisés"
          >
            🌿 Budget Mode {budget ? 'ON' : 'OFF'}
          </button>
        </div>

        {/* View Mode Toggle: Grid Lookbook vs Mannequin Silhouette */}
        <div style={{ display: 'flex', background: 'var(--surface)', padding: '4px', borderRadius: '999px', border: '1px solid var(--line)' }}>
          <button
            className="chip"
            style={{
              padding: '6px 14px',
              fontSize: '0.8rem',
              boxShadow: 'none',
              background: displayMode === 'grid' ? 'var(--pastel-pink-soft)' : 'transparent',
              color: displayMode === 'grid' ? 'var(--pastel-pink-deep)' : 'var(--muted)',
              border: 'none',
              fontWeight: displayMode === 'grid' ? 700 : 500,
            }}
            onClick={() => setDisplayMode('grid')}
          >
            Grille Lookbook
          </button>
          <button
            className="chip"
            style={{
              padding: '6px 14px',
              fontSize: '0.8rem',
              boxShadow: 'none',
              background: displayMode === 'mannequin' ? 'var(--pastel-pink-soft)' : 'transparent',
              color: displayMode === 'mannequin' ? 'var(--pastel-pink-deep)' : 'var(--muted)',
              border: 'none',
              fontWeight: displayMode === 'mannequin' ? 700 : 500,
            }}
            onClick={() => setDisplayMode('mannequin')}
          >
            🪞 Silhouette Mannequin
          </button>
        </div>
      </section>

      {/* Main Visual Outfit Display */}
      {useDemoData && activeOutfit ? (
        displayMode === 'grid' ? (
          <section className="split">
            <div>
              <div className="grid">
                {activeOutfit.items.map((item, i) => (
                  <ItemTile
                    key={item.id}
                    item={item}
                    index={i}
                    onClick={it => setSelectedItem(it)}
                  />
                ))}
              </div>
            </div>

            <aside>
              <div className="card card-lavender" style={{ marginBottom: '20px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                  <span style={{ fontSize: '20px' }}>🪄</span>
                  <h3 style={{ fontSize: '1.15rem', color: 'var(--pastel-lavender-deep)' }}>
                    Justification du Jury & Styliste
                  </h3>
                </div>
                <p style={{ fontSize: '0.94rem', lineHeight: '1.6', color: 'var(--ink)' }}>
                  {activeOutfit.reason}
                </p>

                {activeOutfit.weather && (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                      marginTop: '16px',
                      paddingTop: '14px',
                      borderTop: '1px solid rgba(220, 196, 242, 0.4)',
                      fontSize: '0.85rem',
                      color: 'var(--muted)',
                    }}
                  >
                    <span style={{ fontSize: '18px' }}>🌤️</span>
                    <span>
                      Météo calculée : <strong>{activeOutfit.weather.label}</strong> à{' '}
                      <strong>{activeOutfit.weather.temperatureC}°C</strong>
                    </span>
                  </div>
                )}
              </div>

              <div className="card" style={{ background: '#FFFFFF' }}>
                <h4 style={{ fontSize: '1rem', marginBottom: '10px' }}>Facteurs de Décision Algorithmique</h4>
                <ul style={{ paddingLeft: '20px', margin: 0, fontSize: '0.88rem', color: 'var(--muted)', lineHeight: '1.6' }}>
                  <li>Paires validées à 92% de compatibilité par le réseau de neurones PairMLP.</li>
                  <li>Indice thermique adapté pour une journée à 21°C.</li>
                  <li>Adhérence au persona de style : <strong>{profile.axis}</strong>.</li>
                </ul>
              </div>
            </aside>
          </section>
        ) : (
          <div style={{ maxWidth: '680px', margin: '0 auto' }}>
            <MannequinView
              items={activeOutfit.items}
              tryOnImageUrl={activeOutfit.tryOnImageUrl}
            />
          </div>
        )
      ) : (
        <DataState
          state={apiState}
          endpoint="GET /outfits/today"
          pending="Votre tenue du jour apparaîtra ici dès la connexion aux services d'orchestration."
        >
          {outfit => (
            <section className="split">
              <div className="grid">
                {outfit.items.map((i, idx) => (
                  <ItemTile
                    key={i.id}
                    item={i}
                    index={idx}
                    onClick={it => setSelectedItem(it)}
                  />
                ))}
              </div>
              <div>
                <div className="card card-lavender" style={{ marginBottom: '16px' }}>
                  {outfit.weather && (
                    <p style={{ fontWeight: 600, color: 'var(--pastel-lavender-deep)', marginBottom: '8px' }}>
                      🌤️ {outfit.weather.label}, {outfit.weather.temperatureC}°C
                    </p>
                  )}
                  {outfit.reason && <p style={{ fontSize: '0.95rem', lineHeight: '1.5' }}>{outfit.reason}</p>}
                </div>
              </div>
            </section>
          )}
        </DataState>
      )}

      {/* Item Detail Modal */}
      <ItemDetailModal
        item={selectedItem}
        onClose={() => setSelectedItem(null)}
      />
    </>
  );
}
