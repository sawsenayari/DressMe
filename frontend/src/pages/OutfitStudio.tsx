import { useState } from 'react';
import type { ClothingItem, Slot, OutfitJuryResult } from '../types';
import { useApp } from '../context/AppContext';
import { ItemTile } from '../components/ui/ItemTile';
import { MannequinView } from '../components/ui/MannequinView';
import { evaluateOutfitWithJury } from '../data/sampleData';

const SLOTS: { id: Slot; label: string; icon: string }[] = [
  { id: 'top', label: 'Haut (Top)', icon: '👚' },
  { id: 'bottom', label: 'Bas (Bottom)', icon: '👖' },
  { id: 'onepiece', label: 'Robe / Pièce unique', icon: '👗' },
  { id: 'outer', label: 'Veste / Manteau', icon: '🧥' },
  { id: 'footwear', label: 'Chaussures', icon: '👠' },
  { id: 'bag', label: 'Sac à main', icon: '👜' },
  { id: 'accessory', label: 'Accessoire', icon: '🧣' },
];

const OCCASIONS = [
  { id: 'casual', label: 'Casual Chic', icon: '☕' },
  { id: 'work', label: 'Travail & Bureau', icon: '💼' },
  { id: 'evening', label: 'Soirée Habillée', icon: '🌙' },
];

export default function OutfitStudio() {
  const { wardrobe } = useApp();

  // Selected items composing the outfit
  const [selectedItems, setSelectedItems] = useState<ClothingItem[]>([
    wardrobe[0], // pink sweater
    wardrobe[1], // cream trousers
    wardrobe[3], // court sneakers
  ]);

  const [activeSlotModal, setActiveSlotModal] = useState<Slot | null>(null);
  const [occasion, setOccasion] = useState('casual');
  const [temperature, setTemperature] = useState(21);
  const [juryResult, setJuryResult] = useState<OutfitJuryResult | null>(() =>
    evaluateOutfitWithJury(
      [wardrobe[0], wardrobe[1], wardrobe[3]],
      'casual',
      21
    )
  );

  const [isEvaluating, setIsEvaluating] = useState(false);

  // Trigger Jury de Tenues evaluation
  const runJuryEvaluation = (items: ClothingItem[], occ = occasion, temp = temperature) => {
    setIsEvaluating(true);
    setTimeout(() => {
      const res = evaluateOutfitWithJury(items, occ, temp);
      setJuryResult(res);
      setIsEvaluating(false);
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

  const handleApplyRepair = (problemId: string, replacement: ClothingItem) => {
    const updated = selectedItems.map(i => (i.id === problemId ? replacement : i));
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
          disabled={isEvaluating}
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
                    <span style={{ fontWeight: 600 }}>
                      Score: Math {(juryResult.judges.visual.score01 * 100).toFixed(0)}%
                    </span>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '8px', borderBottom: '1px solid var(--line)' }}>
                    <span>🔗 <strong>Juge Paires (Obj2 PairMLP)</strong></span>
                    <span style={{ fontWeight: 600 }}>
                      Compatibilité: {(juryResult.judges.compatibility.score01 * 100).toFixed(0)}%
                    </span>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '8px', borderBottom: '1px solid var(--line)' }}>
                    <span>🌤️ <strong>Juge Contexte (Météo/Agenda)</strong></span>
                    <span style={{ color: juryResult.judges.context.matchWeather ? 'var(--pastel-mint-deep)' : 'var(--danger)', fontWeight: 600 }}>
                      {juryResult.judges.context.matchWeather ? '✓ Confort adapté' : '⚠️ Inadapté'}
                    </span>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>🤖 <strong>Juge Synthèse LLM</strong></span>
                    <span style={{ fontStyle: 'italic', color: 'var(--muted)' }}>
                      "{juryResult.judges.llm.verdict}"
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
                    Le modèle propose des pièces de substitution issues de votre garde-robe pour hausser la note :
                  </p>

                  {juryResult.repairs.map((rep, idx) => (
                    <div key={idx} style={{ background: '#FFFFFF', padding: '14px', borderRadius: '16px', marginBottom: '10px' }}>
                      <p style={{ fontSize: '0.85rem', color: 'var(--danger)', fontWeight: 600, margin: '0 0 8px' }}>
                        ⚠️ {rep.reason}
                      </p>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                        <span style={{ fontSize: '0.82rem', color: 'var(--muted)' }}>Remplacer par:</span>
                        {rep.suggestedReplacements.map(sug => (
                          <button
                            key={sug.id}
                            className="btn btn-mint btn-sm"
                            style={{ borderRadius: '999px', fontSize: '0.8rem', padding: '6px 12px' }}
                            onClick={() => handleApplyRepair(rep.problemItemId, sug)}
                          >
                            + Remplacer par {sug.name || sug.color}
                          </button>
                        ))}
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
