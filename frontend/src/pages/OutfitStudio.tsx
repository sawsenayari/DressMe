import { useRef, useState } from 'react';
import type { ClothingItem, Occasion, Slot, OutfitJuryResult } from '../types';
import { useApp } from '../context/AppContext';
import { useAsync } from '../hooks/useAsync';
import { ItemTile } from '../components/ui/ItemTile';
import { MannequinView } from '../components/ui/MannequinView';
import { evaluateOutfitWithJury } from '../data/sampleData';
import { judgeOutfit } from '../services/jury';
import { listItems } from '../services/wardrobe';

const SLOTS: { id: Slot; label: string; icon: string }[] = [
  { id: 'top', label: 'Haut (Top)', icon: '👚' },
  { id: 'bottom', label: 'Bas (Bottom)', icon: '👖' },
  { id: 'onepiece', label: 'Robe / Pièce unique', icon: '👗' },
  { id: 'outer', label: 'Veste / Manteau', icon: '🧥' },
  { id: 'footwear', label: 'Chaussures', icon: '👠' },
  { id: 'bag', label: 'Sac à main', icon: '👜' },
  { id: 'accessory', label: 'Accessoire', icon: '🧣' },
];

const OCCASIONS: { id: Occasion; label: string; icon: string }[] = [
  { id: 'casual', label: 'Casual Chic', icon: '☕' },
  { id: 'work', label: 'Travail & Bureau', icon: '💼' },
  { id: 'evening', label: 'Soirée Habillée', icon: '🌙' },
];

export default function OutfitStudio() {
  const { useDemoData } = useApp();
  // Changer de mode repart d'un studio vierge : les pièces de démo sont inconnues du backend, et inversement
  return <Studio key={String(useDemoData)} live={!useDemoData} />;
}

function Studio({ live }: { live: boolean }) {
  const { wardrobe: demoWardrobe } = useApp();

  // Live mode: the backend catalogue, the only ids its jury knows
  const liveWardrobe = useAsync(() => (live ? listItems() : Promise.resolve([])), [live]);
  const wardrobe = live ? liveWardrobe.data ?? [] : demoWardrobe;

  // Selected items composing the outfit
  const [selectedItems, setSelectedItems] = useState<ClothingItem[]>(() => live ? [] : [
    demoWardrobe[0], // pink sweater
    demoWardrobe[1], // cream trousers
    demoWardrobe[3], // court sneakers
  ]);

  const [activeSlotModal, setActiveSlotModal] = useState<Slot | null>(null);
  const [occasion, setOccasion] = useState<Occasion>('casual');
  const [temperature, setTemperature] = useState(21);
  const [juryResult, setJuryResult] = useState<OutfitJuryResult | null>(() =>
    live ? null : evaluateOutfitWithJury(
      [demoWardrobe[0], demoWardrobe[1], demoWardrobe[3]],
      'casual',
      21
    )
  );

  const [isEvaluating, setIsEvaluating] = useState(false);
  const [juryError, setJuryError] = useState<string | null>(null);
  const pendingTimer = useRef<ReturnType<typeof setTimeout>>();
  const lastRun = useRef(0);

  // Trigger Jury de Tenues evaluation
  const runJuryEvaluation = (items: ClothingItem[], occ = occasion, temp = temperature) => {
    clearTimeout(pendingTimer.current); // le curseur de température déclenche une évaluation par cran
    const run = ++lastRun.current;
    setJuryError(null);
    if (live && items.length === 0) {
      setJuryResult(null);
      setIsEvaluating(false);
      return;
    }
    setIsEvaluating(true);
    pendingTimer.current = setTimeout(async () => {
      try {
        const res = live
          ? await judgeOutfit({ item_ids: items.map(i => i.id), occasion: occ, temperatureC: temp })
          : evaluateOutfitWithJury(items, occ, temp);
        if (run === lastRun.current) setJuryResult(res);
      } catch (e) {
        if (run === lastRun.current) {
          setJuryResult(null); // pas d'ancien verdict affiché pour une tenue qui a changé
          setJuryError(e instanceof Error ? e.message : String(e));
        }
      } finally {
        if (run === lastRun.current) setIsEvaluating(false);
      }
    }, 400);
  };

  const handleSelectItemForSlot = (item: ClothingItem) => {
    const withoutSlot = selectedItems.filter(i => {
      if (item.slot === 'onepiece') {
        return i.slot !== 'top' && i.slot !== 'bottom' && i.slot !== 'onepiece';
      }
      if (item.slot === 'top' || item.slot === 'bottom') {
        return i.slot !== item.slot && i.slot !== 'onepiece';
      }
      return i.slot !== item.slot;
    });

    const updated = [...withoutSlot, item];
    setSelectedItems(updated);
    setActiveSlotModal(null);
    runJuryEvaluation(updated);
  };

  const handleRemoveItem = (id: string) => {
    const updated = selectedItems.filter(i => i.id !== id);
    setSelectedItems(updated);
    runJuryEvaluation(updated);
  };

  // Le réparateur de l'Obj3 remplace, ajoute (pas de pièce visée) ou retire (pas de remplaçant)
  const handleApplyRepair = (problemId: string | null, replacement?: ClothingItem) => {
    const updated = problemId === null
      ? [...selectedItems, ...(replacement ? [replacement] : [])]
      : selectedItems.flatMap(i => (i.id !== problemId ? [i] : replacement ? [replacement] : []));
    setSelectedItems(updated);
    runJuryEvaluation(updated);
  };

  return (
    <>
      <header className="page-head">
        <div>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            Outfit Studio & Jury de Tenues <span style={{ fontSize: '1.6rem' }}>⚖️</span>
          </h1>
          <p className="page-subtitle">
            Composez librement votre tenue depuis votre dressing. L'arbitre multi-juges (Objectif 3 & 2) évalue la cohérence et propose des réparations automatiques.
          </p>
        </div>

        <button
          className="btn"
          onClick={() => runJuryEvaluation(selectedItems)}
          disabled={isEvaluating || selectedItems.length === 0}
        >
          <span>⚖️</span>
          <span>{isEvaluating ? 'Délibération du Jury…' : 'Évaluer la Tenue'}</span>
        </button>
      </header>

      {/* Occasion and Context Controls */}
      <section style={{ marginBottom: '24px', display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'center' }}>
        <div className="chips" style={{ marginBottom: 0 }}>
          {OCCASIONS.map(occ => (
            <button
              key={occ.id}
              className="chip"
              aria-pressed={occasion === occ.id}
              onClick={() => {
                setOccasion(occ.id);
                runJuryEvaluation(selectedItems, occ.id, temperature);
              }}
            >
              <span>{occ.icon}</span>
              <span>{occ.label}</span>
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', background: 'var(--surface)', padding: '6px 16px', borderRadius: '999px', border: '1px solid var(--line)' }}>
          <span style={{ fontSize: '0.85rem', color: 'var(--muted)' }}>Météo prévue:</span>
          <input
            type="range"
            min="5"
            max="35"
            value={temperature}
            onChange={e => {
              const t = Number(e.target.value);
              setTemperature(t);
              runJuryEvaluation(selectedItems, occasion, t);
            }}
            style={{ width: '90px', accentColor: 'var(--pastel-pink-deep)' }}
          />
          <strong style={{ fontSize: '0.9rem', minWidth: '38px' }}>{temperature}°C</strong>
        </div>
      </section>

      {/* Main Studio View: Composition Slots on Left, Jury Result & Mannequin on Right */}
      <div className="split" style={{ alignItems: 'start' }}>
        {/* Left Column: Composed Outfit Slots */}
        <div>
          <h3 style={{ fontSize: '1.2rem', marginBottom: '16px' }}>
            Pièces Sélectionnées ({selectedItems.length})
          </h3>

          <div style={{ display: 'grid', gap: '14px' }}>
            {SLOTS.map(slot => {
              const matched = selectedItems.find(i => i.slot === slot.id);

              return (
                <div
                  key={slot.id}
                  style={{
                    background: 'var(--surface)',
                    border: matched ? '1.5px solid var(--pastel-pink)' : '1px dashed var(--line)',
                    borderRadius: '20px',
                    padding: '12px 18px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    boxShadow: matched ? 'var(--shadow-subtle)' : 'none',
                    transition: 'all 0.2s ease',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                    {matched ? (
                      <img
                        src={matched.imageCrop || matched.imageUrl}
                        alt={matched.name || slot.label}
                        style={{ width: '56px', height: '64px', borderRadius: '12px', objectFit: 'cover' }}
                      />
                    ) : (
                      <div
                        style={{
                          width: '56px',
                          height: '64px',
                          borderRadius: '12px',
                          background: 'var(--paper)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: '22px',
                        }}
                      >
                        {slot.icon}
                      </div>
                    )}

                    <div>
                      <div style={{ fontSize: '0.78rem', color: 'var(--muted)', fontWeight: 600, textTransform: 'uppercase' }}>
                        {slot.label}
                      </div>
                      <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--ink)' }}>
                        {matched ? matched.name || matched.color : 'Aucune pièce choisie'}
                      </div>
                      {matched?.traditional && (
                        <span className="chip-tag chip-tag-butter" style={{ fontSize: '0.72rem', marginTop: '2px' }}>
                          🇹🇳 Pièce Traditionnelle
                        </span>
                      )}
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      className="btn-secondary btn-sm"
                      style={{ borderRadius: '999px', fontSize: '0.8rem' }}
                      onClick={() => setActiveSlotModal(slot.id)}
                    >
                      {matched ? 'Changer' : '+ Choisir'}
                    </button>
                    {matched && (
                      <button
                        className="btn-sm"
                        style={{ borderRadius: '999px', background: 'var(--danger-bg)', color: 'var(--danger)', fontSize: '0.8rem' }}
                        onClick={() => handleRemoveItem(matched.id)}
                        title="Retirer cette pièce"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* 2D Mannequin & Try-on Preview */}
          <div style={{ marginTop: '24px' }}>
            <MannequinView items={selectedItems} />
          </div>
        </div>

        {/* Right Column: Jury Decision & Repairs ("Réparateur") */}
        <div>
          {live && liveWardrobe.error && (
            <div className="card card-peach" style={{ padding: '18px', marginBottom: '20px', fontSize: '0.9rem' }}>
              Garde-robe indisponible (GET /wardrobe/items) : {liveWardrobe.error.message}
            </div>
          )}
          {juryError && (
            <div className="card card-peach" style={{ padding: '18px', marginBottom: '20px', fontSize: '0.9rem' }}>
              Jury indisponible (POST /outfits/judge) : {juryError}
            </div>
          )}
          {live && !juryResult && !juryError && !isEvaluating && (
            <div className="card" style={{ padding: '22px', color: 'var(--muted)', fontSize: '0.92rem' }}>
              Composez une tenue depuis votre garde-robe : le jury l'évaluera à chaque changement.
            </div>
          )}
          {juryResult && (
            <div style={{ display: 'grid', gap: '20px' }}>
              {/* Verdict Summary Card */}
              <div
                className={`card ${
                  juryResult.verdict === 'convient'
                    ? 'card-mint'
                    : juryResult.verdict === 'a_ameliorer'
                    ? 'card-butter'
                    : 'card-peach'
                }`}
                style={{ padding: '24px' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <span
                    style={{
                      fontSize: '0.8rem',
                      fontWeight: 800,
                      textTransform: 'uppercase',
                      padding: '4px 12px',
                      borderRadius: '999px',
                      background: '#FFFFFF',
                    }}
                  >
                    Verdict: {juryResult.verdict.toUpperCase()}
                  </span>

                  <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px' }}>
                    <span style={{ fontSize: '2rem', fontWeight: 800 }}>{juryResult.score}</span>
                    <span style={{ fontSize: '0.9rem', color: 'var(--muted)' }}>/100</span>
                  </div>
                </div>

                <h3 style={{ fontSize: '1.25rem', marginBottom: '8px' }}>
                  {juryResult.verdictLabel}
                </h3>
                <p style={{ fontSize: '0.92rem', lineHeight: '1.5', margin: 0 }}>
                  {juryResult.rationale}
                </p>
              </div>

              {/* 5-Judge Deliberation Details */}
              <div className="card" style={{ padding: '22px' }}>
                <h4 style={{ fontSize: '1.05rem', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span>🏛️</span>
                  <span>Délibération des 5 Juges Spécialisés</span>
                </h4>

                <div style={{ display: 'grid', gap: '12px', fontSize: '0.88rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '8px', borderBottom: '1px solid var(--line)' }}>
                    <span>📐 <strong>Juge Règles & Proportions</strong></span>
                    <span style={{ color: juryResult.judges.rules.status === 'pass' ? 'var(--pastel-mint-deep)' : 'var(--danger)', fontWeight: 600 }}>
                      {juryResult.judges.rules.status === 'pass' ? '✓ Valide' : '⚠️ Non conforme'}
                    </span>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '8px', borderBottom: '1px solid var(--line)' }}>
                    <span>🎨 <strong>Juge Visuel (FashionCLIP)</strong></span>
                    <span style={{ fontWeight: 600 }} title={juryResult.judges.visual.message}>
                      {juryResult.judges.visual.score01 == null
                        ? 'Non disponible'
                        : `Score: Math ${(juryResult.judges.visual.score01 * 100).toFixed(0)}%`}
                    </span>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '8px', borderBottom: '1px solid var(--line)' }}>
                    <span>🔗 <strong>Juge Paires (Obj2 PairMLP)</strong></span>
                    <span style={{ fontWeight: 600 }} title={juryResult.judges.compatibility.message}>
                      {juryResult.judges.compatibility.score01 == null
                        ? 'Non disponible'
                        : `Compatibilité: ${(juryResult.judges.compatibility.score01 * 100).toFixed(0)}%`}
                    </span>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '8px', borderBottom: '1px solid var(--line)' }}>
                    <span>🌤️ <strong>Juge Contexte (Météo/Agenda)</strong></span>
                    <span style={{ color: juryResult.judges.context.matchWeather === false ? 'var(--danger)' : juryResult.judges.context.matchWeather ? 'var(--pastel-mint-deep)' : 'var(--muted)', fontWeight: 600 }}>
                      {juryResult.judges.context.matchWeather === null ? 'Météo non évaluée' : juryResult.judges.context.matchWeather ? '✓ Confort adapté' : '⚠️ Inadapté'}
                    </span>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>🤖 <strong>Juge Synthèse LLM</strong></span>
                    <span style={{ fontStyle: 'italic', color: 'var(--muted)' }} title={juryResult.judges.llm.critique}>
                      {juryResult.judges.llm.verdict === 'non disponible' ? 'Non disponible' : `"${juryResult.judges.llm.verdict}"`}
                    </span>
                  </div>
                </div>
              </div>

              {/* Réparation d'Outfit ("Réparateur" from Objectif 3) */}
              {juryResult.repairs.length > 0 && (
                <div className="card card-lavender" style={{ padding: '22px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
                    <span style={{ fontSize: '20px' }}>🔧</span>
                    <h4 style={{ fontSize: '1.05rem', color: 'var(--pastel-lavender-deep)' }}>
                      Suggestions du Réparateur de Tenue
                    </h4>
                  </div>

                  <p style={{ fontSize: '0.88rem', color: 'var(--ink)', marginBottom: '14px' }}>
                    Le modèle propose des corrections à partir de votre garde-robe pour hausser la note :
                  </p>

                  {juryResult.repairs.map((rep, idx) => (
                    <div key={idx} style={{ background: '#FFFFFF', padding: '14px', borderRadius: '16px', marginBottom: '10px' }}>
                      <p style={{ fontSize: '0.85rem', color: 'var(--danger)', fontWeight: 600, margin: '0 0 8px' }}>
                        ⚠️ {rep.reason}
                      </p>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                        {rep.suggestedReplacements.map(sug => (
                          <button
                            key={sug.id}
                            className="btn btn-mint btn-sm"
                            style={{ borderRadius: '999px', fontSize: '0.8rem', padding: '6px 12px' }}
                            onClick={() => handleApplyRepair(rep.problemItemId, sug)}
                          >
                            + {rep.problemItemId === null ? 'Ajouter' : 'Remplacer par'} {sug.name || sug.color}
                          </button>
                        ))}
                        {rep.suggestedReplacements.length === 0 && (
                          <button
                            className="btn btn-mint btn-sm"
                            style={{ borderRadius: '999px', fontSize: '0.8rem', padding: '6px 12px' }}
                            onClick={() => handleApplyRepair(rep.problemItemId)}
                          >
                            Retirer cette pièce
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Item Picker Modal when user clicks "Choisir" on a slot */}
      {activeSlotModal && (
        <div className="modal-backdrop" onClick={() => setActiveSlotModal(null)}>
          <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: '640px' }}>
            <button className="modal-close" onClick={() => setActiveSlotModal(null)}>
              ✕
            </button>

            <h2 style={{ fontSize: '1.3rem', marginBottom: '6px' }}>
              Choisir une pièce : {SLOTS.find(s => s.id === activeSlotModal)?.label}
            </h2>
            <p style={{ color: 'var(--muted)', fontSize: '0.88rem', marginBottom: '18px' }}>
              Sélectionnez une pièce dans votre garde-robe pour ce slot.
            </p>

            <div className="grid small" style={{ maxHeight: '420px', overflowY: 'auto', padding: '4px' }}>
              {wardrobe
                .filter(i => {
                  if (activeSlotModal === 'onepiece') return i.slot === 'onepiece';
                  return i.slot === activeSlotModal;
                })
                .map((item, idx) => (
                  <ItemTile
                    key={item.id}
                    item={item}
                    index={idx}
                    onClick={() => handleSelectItemForSlot(item)}
                  />
                ))}
            </div>

            {wardrobe.filter(i => (activeSlotModal === 'onepiece' ? i.slot === 'onepiece' : i.slot === activeSlotModal)).length === 0 && (
              <div style={{ textAlign: 'center', padding: '24px', color: 'var(--muted)' }}>
                Aucune pièce enregistrée pour ce slot dans votre dressing.
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
