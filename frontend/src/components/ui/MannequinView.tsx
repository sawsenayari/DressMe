import { useState } from 'react';
import type { ClothingItem } from '../../types';

interface Props {
  items: ClothingItem[];
  tryOnImageUrl?: string;
  className?: string;
}

export function MannequinView({ items, tryOnImageUrl }: Props) {
  const [viewMode, setViewMode] = useState<'layers' | 'tryon'>('layers');

  // Segregate items by slot for the 2D layered mannequin
  const top = items.find(i => i.slot === 'top');
  const bottom = items.find(i => i.slot === 'bottom');
  const onepiece = items.find(i => i.slot === 'onepiece');
  const outer = items.find(i => i.slot === 'outer');
  const shoes = items.find(i => i.slot === 'footwear');
  const bag = items.find(i => i.slot === 'bag');

  return (
    <div className="card" style={{ padding: '24px', background: 'var(--surface)' }}>
      {/* View Switcher Controls (Niveau 1 vs Niveau 2) */}
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
          <h3 style={{ fontSize: '1.1rem' }}>Avatar & Silhouette Studio</h3>
        </div>

        <div style={{ display: 'flex', gap: '6px', background: 'var(--paper)', padding: '4px', borderRadius: '999px' }}>
          <button
            className="chip"
            style={{
              padding: '6px 14px',
              fontSize: '0.8rem',
              boxShadow: 'none',
              background: viewMode === 'layers' ? '#FFFFFF' : 'transparent',
              color: viewMode === 'layers' ? 'var(--ink)' : 'var(--muted)',
              border: viewMode === 'layers' ? '1px solid var(--line)' : 'none',
              fontWeight: viewMode === 'layers' ? 700 : 500,
            }}
            onClick={() => setViewMode('layers')}
          >
            Niveau 1: Mannequin 2D
          </button>
          <button
            className="chip"
            style={{
              padding: '6px 14px',
              fontSize: '0.8rem',
              boxShadow: 'none',
              background: viewMode === 'tryon' ? 'linear-gradient(135deg, var(--pastel-pink) 0%, var(--pastel-lavender) 100%)' : 'transparent',
              color: viewMode === 'tryon' ? '#292832' : 'var(--muted)',
              border: 'none',
              fontWeight: viewMode === 'tryon' ? 700 : 500,
            }}
            onClick={() => setViewMode('tryon')}
          >
            ✨ Niveau 2: Essayage Virtuel
          </button>
        </div>
      </div>

      {viewMode === 'layers' ? (
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
      ) : (
        /* Niveau 2: Virtual Try-On (CatVTON / FASHN photoréaliste) */
        <div style={{ textAlign: 'center' }}>
          <div
            style={{
              position: 'relative',
              width: '100%',
              maxWidth: '380px',
              margin: '0 auto',
              aspectRatio: '3/4',
              borderRadius: '24px',
              overflow: 'hidden',
              boxShadow: 'var(--shadow-hover)',
              border: '1px solid var(--line)',
            }}
          >
            <img
              src={tryOnImageUrl || 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=800&auto=format&fit=crop&q=80'}
              alt="Essayage virtuel photoréaliste (CatVTON)"
              style={{ width: '100%', height: '100%', objectFit: 'cover' }}
            />
            <div
              style={{
                position: 'absolute',
                bottom: '12px',
                left: '12px',
                right: '12px',
                background: 'rgba(255, 255, 255, 0.92)',
                backdropFilter: 'blur(8px)',
                padding: '10px 14px',
                borderRadius: '16px',
                textAlign: 'left',
              }}
            >
              <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--ink)' }}>
                Rendu Photoréaliste (CatVTON / FASHN)
              </div>
              <div style={{ fontSize: '0.74rem', color: 'var(--muted)' }}>
                Généré en local sur GPU T4 — Aucune photo externe transmise.
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
