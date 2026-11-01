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
  { id: 'top', label: 'Haut', icon: '👚' },
  { id: 'bottom', label: 'Bas', icon: '👖' },
  { id: 'onepiece', label: 'Robe / Pièce unique', icon: '👗' },
  { id: 'outer', label: 'Veste / Manteau', icon: '🧥' },
  { id: 'footwear', label: 'Chaussures', icon: '👠' },
  { id: 'bag', label: 'Sac à main', icon: '👜' },
  { id: 'accessory', label: 'Accessoire', icon: '🧣' },
];

const OCCASIONS: { id: Occasion; label: string; icon: string }[] = [
  { id: 'casual', label: 'Décontracté', icon: '☕' },
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

  // Une pièce par emplacement : une robe remplace haut + bas, un haut ou un bas remplace la robe
  const withItem = (list: ClothingItem[], item: ClothingItem) => [
    ...list.filter(i => {
      if (i.id === item.id) return false;
      if (item.slot === 'onepiece') return i.slot !== 'top' && i.slot !== 'bottom' && i.slot !== 'onepiece';
      if (item.slot === 'top' || item.slot === 'bottom') return i.slot !== item.slot && i.slot !== 'onepiece';
      return i.slot !== item.slot;
    }),
    item,
  ];

  const handleSelectItemForSlot = (item: ClothingItem) => {
    const updated = withItem(selectedItems, item);
    setSelectedItems(updated);
    setActiveSlotModal(null);
    runJuryEvaluation(updated);
  };

  const handleRemoveItem = (id: string) => {
    const updated = selectedItems.filter(i => i.id !== id);
    setSelectedItems(updated);
    runJuryEvaluation(updated);
  };


  return (
    <>
      <header className="page-head">
        <div>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            Composer une tenue <span style={{ fontSize: '1.6rem' }}>⚖️</span>
          </h1>
          <p className="page-subtitle">
            Composez une tenue avec vos pièces : notre jury de style vous dit si elle convient à l'occasion et à la météo, et pourquoi.
          </p>
        </div>

        <button
          className="btn"
          onClick={() => runJuryEvaluation(selectedItems)}
          disabled={isEvaluating || selectedItems.length === 0}
        >
          <span>⚖️</span>
          <span>{isEvaluating ? 'Évaluation…' : 'Évaluer la tenue'}</span>
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
          <span style={{ fontSize: '0.85rem', color: 'var(--muted)' }}>Température :</span>
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
              Votre garde-robe n'a pas pu être chargée : {liveWardrobe.error.message}
            </div>
          )}
          {juryError && (
            <div className="card card-peach" style={{ padding: '18px', marginBottom: '20px', fontSize: '0.9rem' }}>
              L'évaluation n'a pas pu être faite : {juryError}
            </div>
          )}
          {live && !juryResult && !juryError && !isEvaluating && (
            <div className="card" style={{ padding: '22px', color: 'var(--muted)', fontSize: '0.92rem' }}>
              Choisissez des pièces de votre garde-robe : la tenue est évaluée à chaque changement.
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
                    Verdict : {({ convient: 'convient', a_ameliorer: 'à améliorer', deconseille: 'déconseillé' } as const)[juryResult.verdict]}
                  </span>

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
                  <span>Le détail de l'évaluation</span>
                </h4>

                <div style={{ display: 'grid', gap: '12px', fontSize: '0.88rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '8px', borderBottom: '1px solid var(--line)' }}>
                    <span>📐 <strong>Règles de style</strong></span>
                    <span style={{ color: juryResult.judges.rules.status === 'pass' ? 'var(--pastel-mint-deep)' : juryResult.judges.rules.status === 'warn' ? 'var(--pastel-butter-deep)' : 'var(--danger)', fontWeight: 600 }}
                          title={juryResult.judges.rules.message}>
                      {juryResult.judges.rules.status === 'pass' ? '✓ Valide' : juryResult.judges.rules.status === 'warn' ? '⚠️ Réserves' : '✗ Non conforme'}
                    </span>
                  </div>

                  <div style={{ paddingBottom: '8px', borderBottom: '1px solid var(--line)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>🎨 <strong>Analyse des photos</strong></span>
                      <span style={{ fontWeight: 600, color: juryResult.judges.visual.score01 == null ? 'var(--muted)' : juryResult.judges.visual.status === 'pass' ? 'var(--pastel-mint-deep)' : juryResult.judges.visual.status === 'warn' ? 'var(--pastel-butter-deep)' : 'var(--danger)' }}>
                        {juryResult.judges.visual.score01 == null
                          ? 'Non disponible'
                          : `${juryResult.judges.visual.status === 'pass' ? '✓' : juryResult.judges.visual.status === 'warn' ? '⚠️' : '✗'} ${(juryResult.judges.visual.score01 * 100).toFixed(0)} %`}
                      </span>
                    </div>
                    <p style={{ margin: '4px 0 0', fontSize: '0.78rem', color: 'var(--muted)', fontStyle: juryResult.judges.visual.score01 == null ? 'normal' : 'italic' }}>
                      {juryResult.judges.visual.message}
                    </p>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '8px', borderBottom: '1px solid var(--line)' }}>
                    <span>🔗 <strong>Accord entre les pièces</strong></span>
                    <span style={{ fontWeight: 600 }} title={juryResult.judges.compatibility.message}>
                      {juryResult.judges.compatibility.score01 == null
                        ? 'Non disponible'
                        : `${(juryResult.judges.compatibility.score01 * 100).toFixed(0)} %`}
                    </span>
                  </div>

                  <div style={{ paddingBottom: '8px', borderBottom: '1px solid var(--line)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px' }}>
                      <span>🌤️ <strong>Météo et occasion</strong></span>
                      <span style={{ fontWeight: 600, textAlign: 'right' }}>
                        {(() => {
                          const ctx = juryResult.judges.context;
                          const lvl = (l: number | null | undefined, ok: boolean | null) => (l ?? (ok === null ? null : ok ? 2 : 0));
                          const txt = (l: number | null) => (l === null ? '— non évaluée' : l === 2 ? '✓ adaptée' : l === 1 ? '⚠️ à ajuster' : '✗ inadaptée');
                          return `Météo ${txt(lvl(ctx.weatherLevel, ctx.matchWeather))} · Occasion ${txt(lvl(ctx.occasionLevel, ctx.matchOccasion))}`;
                        })()}
                      </span>
                    </div>
                    <p style={{ margin: '4px 0 0', fontSize: '0.78rem', color: 'var(--muted)' }}>{juryResult.judges.context.message}</p>
                  </div>

                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px' }}>
                      <span>🤖 <strong>Avis de l'IA</strong></span>
                      <span style={{ fontWeight: 600, color: juryResult.judges.llm.verdict === 'non disponible' ? 'var(--muted)' : 'var(--ink)', textAlign: 'right' }}>
                        {juryResult.judges.llm.verdict === 'non disponible' ? 'Non disponible' : juryResult.judges.llm.verdict}
                      </span>
                    </div>
                    {juryResult.judges.llm.critique && (
                      <p style={{ margin: '6px 0 0', fontSize: '0.82rem', fontStyle: 'italic', color: 'var(--muted)', lineHeight: 1.45 }}>
                        {juryResult.judges.llm.critique}
                      </p>
                    )}
                  </div>
                </div>
              </div>

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
