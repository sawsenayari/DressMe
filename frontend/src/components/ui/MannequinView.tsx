import { useEffect, useState } from 'react';
import type { ClothingItem } from '../../types';
import { inspireOutfit, tryOnOutfit, type TryOnResult } from '../../services/outfits';

interface Props {
  items: ClothingItem[];
  className?: string;
}

type Mode = 'real' | 'inspire';
const RUN: Record<Mode, (ids: string[]) => Promise<TryOnResult>> = { real: tryOnOutfit, inspire: inspireOutfit };

/** Silhouette en couches construite avec les photos des pièces choisies ; essayage réaliste (photos portées par un
 *  mannequin, quota quotidien) ; tenue inspirée (photo de mode générée d'après les descriptions des photos, illimitée).
 *  Les deux derniers sont calculés par le serveur seulement sur demande. */
export function MannequinView({ items }: Props) {
  const [view, setView] = useState<'2d' | Mode>('2d');
  const [results, setResults] = useState<Partial<Record<Mode, TryOnResult>>>({});
  const [busy, setBusy] = useState<Partial<Record<Mode, boolean>>>({});
  const [errors, setErrors] = useState<Partial<Record<Mode, string>>>({});
  const key = items.map(i => i.id).join(',');
  useEffect(() => { setResults({}); setErrors({}); setView('2d'); }, [key]);
  const wearable = items.some(i => ['top', 'outer', 'bottom', 'onepiece'].includes(i.slot));

  const run = (mode: Mode, retry = false) => {
    setView(mode);
    if ((results[mode] && !retry) || busy[mode]) return;
    setBusy(b => ({ ...b, [mode]: true })); setErrors(e => ({ ...e, [mode]: undefined }));
    RUN[mode](items.map(i => i.id))
      .then(r => setResults(x => ({ ...x, [mode]: r })))
      .catch((e: Error) => setErrors(x => ({ ...x, [mode]: e.message })))
      .finally(() => setBusy(b => ({ ...b, [mode]: false })));
  };
  const mode: Mode = view === 'inspire' ? 'inspire' : 'real';
  const tryOn = results[mode] ?? null, tryOnBusy = !!busy[mode], tryOnError = errors[mode] ?? null;
  const beside = tryOn ? items.filter(i => !tryOn.worn.includes(i.id)) : [];

  // Segregate items by slot for the 2D layered mannequin
  const top = items.find(i => i.slot === 'top');
  const bottom = items.find(i => i.slot === 'bottom');
  const onepiece = items.find(i => i.slot === 'onepiece');
  const outer = items.find(i => i.slot === 'outer');
  const shoes = items.find(i => i.slot === 'footwear');
  const bag = items.find(i => i.slot === 'bag');

  return (
    <div className="card" style={{ padding: '24px', background: 'var(--surface)' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '20px',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '1.2rem' }}>🪞</span>
          <h3 style={{ fontSize: '1.1rem' }}>Aperçu de la tenue</h3>
        </div>
        <div style={{ display: 'flex', gap: '6px' }}>
          <button className={`btn-sm ${view === '2d' ? '' : 'btn-secondary'}`} style={{ borderRadius: '999px', fontSize: '0.8rem' }}
                  onClick={() => setView('2d')}>Silhouette</button>
          <button className={`btn-sm ${view === 'real' ? '' : 'btn-secondary'}`} style={{ borderRadius: '999px', fontSize: '0.8rem' }}
                  disabled={!wearable} title={wearable ? 'Vos photos portées par un mannequin (IA)' : 'Choisissez un haut, un bas ou une robe'}
                  onClick={() => run('real')}>📸 Essayage réaliste</button>
          <button className={`btn-sm ${view === 'inspire' ? '' : 'btn-secondary'}`} style={{ borderRadius: '999px', fontSize: '0.8rem' }}
                  title="Photo de mode générée d'après la description de vos pièces (illimité, moins fidèle)"
                  onClick={() => run('inspire')}>✨ Inspirée</button>
        </div>
      </div>

      {view !== '2d' ? (
        <div style={{ maxWidth: '380px', margin: '0 auto', display: 'grid', gap: '12px' }}>
          {tryOnBusy && (
            <div style={{ minHeight: '420px', borderRadius: '24px', border: '1px dashed var(--line)', display: 'flex', flexDirection: 'column',
                          alignItems: 'center', justifyContent: 'center', gap: '10px', color: 'var(--muted)', textAlign: 'center', padding: '24px' }}>
              <span style={{ fontSize: '2rem' }}>🧵</span>
              <strong style={{ color: 'var(--ink)' }}>{mode === 'real' ? 'Essayage en cours…' : 'Création de la photo…'}</strong>
              <span style={{ fontSize: '0.85rem' }}>{mode === 'real'
                ? 'Le mannequin enfile vos pièces une à une : comptez de 30 secondes à 2 minutes.'
                : 'L’IA décrit vos pièces puis compose la photo : une vingtaine de secondes.'}</span>
            </div>
          )}
          {tryOnError && !tryOnBusy && (
            <div className="card card-peach" style={{ padding: '16px', fontSize: '0.88rem' }}>
              {mode === 'real' ? 'L’essayage' : 'La photo'} n'a pas pu être faite : {tryOnError}
              <div style={{ marginTop: '10px' }}>
                <button className="btn-sm btn-secondary" onClick={() => run(mode, true)}>Réessayer</button>
              </div>
            </div>
          )}
          {tryOn && !tryOnBusy && (
            <>
              <img src={tryOn.imageUrl} alt="Essayage réaliste de la tenue"
                   style={{ width: '100%', borderRadius: '24px', border: '1px solid var(--line)', boxShadow: 'var(--shadow-card)' }} />
              {tryOn.note && <div className="card card-peach" style={{ padding: '12px', fontSize: '0.85rem' }}>{tryOn.note}</div>}
              {beside.length > 0 && (
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'center' }}>
                  {beside.map(i => (
                    <div key={i.id} title={i.name} style={{ width: '64px', height: '64px', borderRadius: '14px', overflow: 'hidden', background: '#FFFFFF', border: '1px solid var(--line)' }}>
                      <img src={i.imageCrop || i.imageUrl} alt={i.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                    </div>
                  ))}
                </div>
              )}
              <span style={{ fontSize: '0.78rem', color: 'var(--muted)', textAlign: 'center' }}>
                {mode === 'real' ? 'Image générée par IA à partir de vos photos' : 'Photo imaginée par IA d’après la description de vos pièces (moins fidèle que l’essayage)'}
                {beside.length ? ' ; les autres pièces sont montrées à côté' : ''}.
              </span>
            </>
          )}
        </div>
      ) : (
        /* Niveau 1: 2D Layered Mannequin (garanti, non-bloquant) */
        <div
          style={{
            position: 'relative',
            width: '100%',
            maxWidth: '380px',
            margin: '0 auto',
            minHeight: '520px',
            background: 'linear-gradient(180deg, #FDFBFF 0%, #F5F2FA 100%)',
            borderRadius: '24px',
            border: '1px solid var(--line)',
            padding: '24px 16px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'space-between',
            boxShadow: 'inset 0 2px 10px rgba(0,0,0,0.02)',
          }}
        >
          {/* Subtle anatomical mannequin backdrop guide */}
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              pointerEvents: 'none',
              opacity: 0.08,
            }}
          >
            <div style={{ width: '60px', height: '60px', borderRadius: '50%', background: '#292832', marginBottom: '8px' }} />
            <div style={{ width: '120px', height: '180px', borderRadius: '24px', background: '#292832', marginBottom: '8px' }} />
            <div style={{ width: '90px', height: '220px', borderRadius: '18px', background: '#292832' }} />
          </div>

          {/* Layer: Outerwear (placed around/over top) */}
          {outer && (
            <div
              style={{
                position: 'absolute',
                top: '50px',
                right: '18px',
                width: '100px',
                height: '130px',
                borderRadius: '16px',
                overflow: 'hidden',
                background: '#FFFFFF',
                boxShadow: 'var(--shadow-card)',
                border: '1.5px solid var(--pastel-mint)',
                zIndex: 3,
                textAlign: 'center',
              }}
              title={`Outerwear: ${outer.name || outer.color}`}
            >
              <img src={outer.imageCrop || outer.imageUrl} alt="Outerwear" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              <span style={{ position: 'absolute', bottom: 2, left: 4, right: 4, background: 'rgba(255,255,255,0.85)', fontSize: '9px', fontWeight: 700, borderRadius: '4px' }}>
                Veste
              </span>
            </div>
          )}

          {/* Layer: Head/Accessories */}
          <div style={{ width: '54px', height: '54px', borderRadius: '50%', background: 'var(--pastel-lavender-soft)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '24px', zIndex: 1, border: '2px solid #FFFFFF' }}>
            👒
          </div>

          {/* Layer: Top / Onepiece */}
          <div style={{ width: '150px', height: '150px', position: 'relative', zIndex: 2 }}>
            {onepiece ? (
              <div style={{ width: '100%', height: '220px', borderRadius: '20px', overflow: 'hidden', background: '#FFFFFF', boxShadow: 'var(--shadow-card)', border: '2px solid var(--pastel-pink)' }}>
                <img src={onepiece.imageCrop || onepiece.imageUrl} alt="Onepiece" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              </div>
            ) : top ? (
              <div style={{ width: '100%', height: '100%', borderRadius: '18px', overflow: 'hidden', background: '#FFFFFF', boxShadow: 'var(--shadow-card)', border: '2px solid var(--pastel-pink)' }}>
                <img src={top.imageCrop || top.imageUrl} alt="Top" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              </div>
            ) : (
              <div style={{ width: '100%', height: '100%', borderRadius: '18px', border: '2px dashed var(--line)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted)', fontSize: '0.8rem' }}>
                Haut manquant
              </div>
            )}
          </div>

          {/* Layer: Bottom (if not onepiece) */}
          {!onepiece && (
            <div style={{ width: '135px', height: '160px', marginTop: '8px', zIndex: 2 }}>
              {bottom ? (
                <div style={{ width: '100%', height: '100%', borderRadius: '18px', overflow: 'hidden', background: '#FFFFFF', boxShadow: 'var(--shadow-card)', border: '2px solid var(--pastel-lavender)' }}>
                  <img src={bottom.imageCrop || bottom.imageUrl} alt="Bottom" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                </div>
              ) : (
                <div style={{ width: '100%', height: '100%', borderRadius: '18px', border: '2px dashed var(--line)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted)', fontSize: '0.8rem' }}>
                  Bas manquant
                </div>
              )}
            </div>
          )}

          {/* Layer: Shoes & Handbag */}
          <div style={{ display: 'flex', justifyContent: 'space-between', width: '85%', marginTop: '12px', alignItems: 'flex-end', zIndex: 2 }}>
            {bag ? (
              <div style={{ width: '75px', height: '80px', borderRadius: '14px', overflow: 'hidden', background: '#FFFFFF', boxShadow: 'var(--shadow-card)', border: '1.5px solid var(--pastel-butter)' }} title={`Sac: ${bag.name}`}>
                <img src={bag.imageCrop || bag.imageUrl} alt="Bag" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              </div>
            ) : <div style={{ width: '75px' }} />}

            {shoes ? (
              <div style={{ width: '110px', height: '85px', borderRadius: '16px', overflow: 'hidden', background: '#FFFFFF', boxShadow: 'var(--shadow-card)', border: '2px solid var(--pastel-mint)' }} title={`Chaussures: ${shoes.name}`}>
                <img src={shoes.imageCrop || shoes.imageUrl} alt="Shoes" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              </div>
            ) : (
              <div style={{ width: '110px', height: '70px', borderRadius: '14px', border: '2px dashed var(--line)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted)', fontSize: '0.75rem' }}>
                Chaussures
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
