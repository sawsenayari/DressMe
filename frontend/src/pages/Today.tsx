import { useState } from 'react';
import { useAsync } from '../hooks/useAsync';
import { getOutfitOfDay, sendOutfitFeedback } from '../services/outfits';
import type { Occasion, ClothingItem } from '../types';
import { DataState } from '../components/ui/DataState';
import { ItemTile } from '../components/ui/ItemTile';
import { ItemDetailModal } from '../components/ui/ItemDetailModal';
import { MannequinView } from '../components/ui/MannequinView';
import { useApp } from '../context/AppContext';

// Un seul filtre de contexte : il fixe l'occasion transmise à l'Obj6 (tenue) et au jury de l'Obj3 (vérification)
const CONTEXTS: { id: Occasion; label: string; title: string }[] = [
  { id: 'casual', label: '☕ Journée décontractée', title: 'Décontracté' },
  { id: 'work', label: '💼 Travail / réunion', title: 'Travail' },
  { id: 'evening', label: '🌙 Soirée / dîner', title: 'Soirée' },
  { id: 'sport', label: '🏃 Sport', title: 'Sport' },
  { id: 'ceremony', label: '💍 Mariage / cérémonie', title: 'Cérémonie' },
];
const AXIS_FR: Record<string, string> = { efficiency: 'Efficacité', economy: 'Économie', brand: 'Image', mixte: 'Équilibre' };

export default function Today() {
  const { useDemoData, getDemoOutfit, wardrobe, profile } = useApp();
  const [occasion, setOccasion] = useState<Occasion>('casual');
  const budget = false;   // le mode budget n'est pas géré par l'objectif 6 : pas de bouton tant qu'il ne fait rien
  const [exclude, setExclude] = useState<string[][]>([]);   // tenues écartées par « Autre proposition »
  const [feedbackState, setFeedbackState] = useState<'idle' | 'accepted' | 'rejected'>('idle');
  const [feedbackMsg, setFeedbackMsg] = useState('');
  const [busy, setBusy] = useState(false);
  const [selectedItem, setSelectedItem] = useState<ClothingItem | null>(null);
  const [displayMode, setDisplayMode] = useState<'grid' | 'mannequin'>('grid');

  // Live model backend query (Obj6 -> jury Obj3 + compatibilité Obj2)
  const apiState = useAsync(() => getOutfitOfDay(occasion, budget, undefined, exclude), [occasion, exclude]);

  // Demo outfit fallback
  const demoOutfit = getDemoOutfit(occasion, budget);
  const activeOutfit = useDemoData ? demoOutfit : apiState.data;

  const flash = (state: 'accepted' | 'rejected', msg: string) => {
    setFeedbackState(state); setFeedbackMsg(msg);
    setTimeout(() => { setFeedbackState('idle'); setFeedbackMsg(''); }, 3500);
  };

  const changeOccasion = (o: Occasion) => { setOccasion(o); setExclude([]); };
  const context = CONTEXTS.find(c => c.id === occasion) || CONTEXTS[0];

  // « Valider & Porter » : avis positif mémorisé par l'Obj6 (pièces favorisées et marquées portées aujourd'hui)
  const handleAcceptOutfit = async () => {
    if (useDemoData || !apiState.data) { flash('accepted', ''); return; }
    setBusy(true);
    try {
      const r = await sendOutfitFeedback(apiState.data.items.map(i => i.id), true, apiState.data.features);
      flash('accepted', `C'est noté ! Vos prochaines suggestions en tiendront compte (${r.accepted} tenue(s) validée(s)).`);
    } catch (e) {
      flash('rejected', `Avis non enregistré : ${e instanceof Error ? e.message : e}`);
    } finally { setBusy(false); }
  };

  // « Autre proposition » : nouvelle tenue en écartant celle-ci (sans pénaliser ses pièces)
  const handleRejectOutfit = () => {
    if (useDemoData || !apiState.data?.excludeKey) { flash('rejected', ''); return; }
    setExclude(prev => [...prev, apiState.data!.excludeKey!]);
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
              Une tenue choisie pour vous selon la météo, votre journée et votre style.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <button
              className={`btn-sm ${feedbackState === 'accepted' ? 'btn-mint' : 'btn-secondary'}`}
              style={{ borderRadius: '999px', fontWeight: 600 }}
              onClick={handleAcceptOutfit}
              disabled={busy || (!useDemoData && !apiState.data)}
            >
              {feedbackState === 'accepted' ? '✓ Portée aujourd\'hui !' : busy ? 'Envoi…' : '✨ Valider & Porter'}
            </button>
            <button
              className="btn-secondary btn-sm"
              style={{ borderRadius: '999px', fontSize: '0.8rem' }}
              onClick={handleRejectOutfit}
              disabled={!useDemoData && (apiState.loading || !apiState.data)}
            >
              {feedbackState === 'rejected' && useDemoData ? 'Noté pour l\'IA' : '↻ Autre proposition'}
            </button>
          </div>
        </div>

        {(feedbackMsg || (!useDemoData && exclude.length > 0)) && (
          <p role="status" style={{ fontSize: '0.84rem', color: feedbackState === 'rejected' ? 'var(--danger)' : 'var(--muted)', margin: '10px 0 0' }}>
            {feedbackMsg}
            {!useDemoData && exclude.length > 0 && (
              <>
                {feedbackMsg ? ' · ' : ''}{exclude.length} tenue(s) écartée(s){' '}
                <button className="btn-sm btn-secondary" style={{ borderRadius: '999px', fontSize: '0.74rem' }} onClick={() => setExclude([])}>
                  Réinitialiser
                </button>
              </>
            )}
          </p>
        )}

        {/* Contexte du jour : filtre unique (occasion pour l'Obj6 et le jury) */}
        <div style={{ marginTop: '16px', background: 'var(--surface)', padding: '12px 18px', borderRadius: '18px', border: '1px solid var(--line)' }}>
          <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--ink)', display: 'block', marginBottom: '10px' }}>
            📅 Contexte du jour :
          </span>
          <div className="chips" role="group" aria-label="Contexte du jour" style={{ marginBottom: 0 }}>
            {CONTEXTS.map(c => (
              <button key={c.id} className="chip" aria-pressed={c.id === occasion} onClick={() => changeOccasion(c.id)}>
                {c.label}
              </button>
            ))}
          </div>
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
                Contexte
              </span>
              <span style={{ fontSize: '18px' }}>👗</span>
            </div>
            <div style={{ fontSize: '1.5rem', fontWeight: 800, marginTop: '8px', color: 'var(--ink)' }}>
              {context.title}
            </div>
            <div style={{ fontSize: '0.82rem', color: 'var(--muted)', marginTop: '2px' }}>
              Tenue choisie pour ce contexte
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
              {activeOutfit?.compat01 != null ? `${Math.round(activeOutfit.compat01 * 100)} / 100` : '—'}
            </div>
            <div style={{ fontSize: '0.82rem', color: 'var(--muted)', marginTop: '2px' }}>
              {activeOutfit?.compat01 != null ? 'Accord entre les pièces' : 'Pas encore calculable'}
            </div>
          </div>

          <div className="card card-butter" style={{ padding: '18px 20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--pastel-butter-deep)', textTransform: 'uppercase' }}>
                Jury de style
              </span>
              <span style={{ fontSize: '18px' }}>⚖️</span>
            </div>
            <div style={{ fontSize: '1.5rem', fontWeight: 800, marginTop: '8px', color: 'var(--ink)' }}>
              {!activeOutfit ? '—' : activeOutfit.warnings?.length ? 'Avec réserves' : 'Validée'}
            </div>
            <div style={{ fontSize: '0.82rem', color: 'var(--muted)', marginTop: '2px' }}>
              {!activeOutfit ? 'En attente de la tenue' : activeOutfit.warnings?.length ? `${activeOutfit.warnings.length} point(s) d'attention` : 'Rien à signaler'}
            </div>
          </div>

          <div className="card card-lavender" style={{ padding: '18px 20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--pastel-lavender-deep)', textTransform: 'uppercase' }}>
                Météo
              </span>
              <span style={{ fontSize: '18px' }}>⛅</span>
            </div>
            <div style={{ fontSize: '1.5rem', fontWeight: 800, marginTop: '8px', color: 'var(--ink)' }}>
              {activeOutfit?.weather ? `${activeOutfit.weather.temperatureC}°C` : '—'}
            </div>
            <div style={{ fontSize: '0.82rem', color: 'var(--muted)', marginTop: '2px' }}>
              {activeOutfit?.weather?.label ?? "Fournie par l'objectif 6"}
            </div>
          </div>
        </div>
      </section>

      {/* Occasion & Display Mode Switcher (Grid vs Mannequin) */}
      <section style={{ marginBottom: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '14px' }}>
        <span />

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
            Vue en grille
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
            🪞 Vue silhouette
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
                  <ItemTile eager
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
                  <li>Pièces choisies pour bien s'accorder entre elles.</li>
                  <li>Indice thermique adapté pour une journée à 21°C.</li>
                  <li>Adaptée à votre priorité : <strong>{AXIS_FR[profile.axis] || profile.axis}</strong>.</li>
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
          pending={apiState.error ? `Tenue indisponible : ${apiState.error.message}` : "Votre tenue du jour apparaîtra ici dès la connexion aux services d'orchestration."}
        >
          {outfit => (
            <section className="split">
              <div className="grid">
                {outfit.items.map((i, idx) => (
                  <ItemTile eager
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
                {!!outfit.warnings?.length && (
                  <div className="card" style={{ background: '#FFFFFF' }}>
                    <h4 style={{ fontSize: '1rem', marginBottom: '10px' }}>Points d'attention</h4>
                    <ul style={{ paddingLeft: '20px', margin: 0, fontSize: '0.88rem', color: 'var(--muted)', lineHeight: '1.6' }}>
                      {outfit.warnings.map(w => <li key={w}>{w}</li>)}
                    </ul>
                  </div>
                )}
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
