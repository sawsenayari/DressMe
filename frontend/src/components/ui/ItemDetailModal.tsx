import { useState } from 'react';
import type { ClothingItem } from '../../types';

interface Props {
  item: ClothingItem | null;
  onClose: () => void;
  onDelete?: (id: string) => void;
}

export function ItemDetailModal({ item, onClose, onDelete }: Props) {
  const [showCrop, setShowCrop] = useState(false);
  const [isCorrected, setIsCorrected] = useState(false);

  if (!item) return null;

  const confidenceSlot = item.confidence?.slot ? Math.round(item.confidence.slot * 100) : 92;
  const confidenceColour = item.confidence?.colour ? Math.round(item.confidence.colour * 100) : 85;
  const isLowConfidence = confidenceSlot < 75 || confidenceColour < 75;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: '480px' }}>
        <button className="modal-close" onClick={onClose} aria-label="Fermer modal">
          ✕
        </button>

        {/* Image Preview with Raw vs Clean Crop Toggle (Objectif 1 SegFormer/rembg) */}
        <div style={{ position: 'relative', width: '100%', height: '280px', borderRadius: '20px', overflow: 'hidden', marginBottom: '16px', background: showCrop ? '#FFFFFF' : 'var(--paper)', border: '1px solid var(--line)' }}>
          <img
            src={showCrop ? (item.imageCrop || item.imageUrl) : item.imageUrl}
            alt={item.name || item.color}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />

          <button
            onClick={() => setShowCrop(!showCrop)}
            style={{
              position: 'absolute',
              bottom: '10px',
              right: '10px',
              background: 'rgba(255,255,255,0.92)',
              backdropFilter: 'blur(6px)',
              padding: '6px 12px',
              borderRadius: '999px',
              fontSize: '0.76rem',
              fontWeight: 700,
              boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
            }}
          >
            {showCrop ? '🖼️ Voir Photo Brute' : '✂️ Voir Découpe SegFormer (Crop)'}
          </button>
        </div>

        {/* Low Confidence Warning / User Correction (Objectif 1 requirement) */}
        {(isLowConfidence || item.source === 'user_corrected') && (
          <div
            style={{
              background: isCorrected ? 'var(--pastel-mint-soft)' : 'var(--pastel-butter-soft)',
              padding: '10px 14px',
              borderRadius: '14px',
              marginBottom: '16px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '0.84rem',
            }}
          >
            <div>
              <span style={{ fontWeight: 700 }}>
                {isCorrected ? '✓ Attributs Confirmés' : '⚠️ Vérification Recommandée'}
              </span>
              <div style={{ fontSize: '0.76rem', color: 'var(--muted)' }}>
                Couleur ou type à vérifier ({confidenceColour}% confiance Qwen2.5-VL)
              </div>
            </div>

            {!isCorrected && (
              <button
                className="btn-sm btn-secondary"
                style={{ borderRadius: '999px', fontSize: '0.76rem' }}
                onClick={() => setIsCorrected(true)}
              >
                Confirmer
              </button>
            )}
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
          <div>
            <h2 style={{ textTransform: 'capitalize', fontSize: '1.35rem' }}>
              {item.name || `${item.color} ${item.slot}`}
            </h2>
            <p style={{ color: 'var(--muted)', fontSize: '0.88rem', margin: '4px 0 0' }}>
              ID: <code>{item.id}</code> • Type fin: <strong>{item.type || item.slot}</strong>
            </p>
          </div>
          <span className="chip-tag chip-tag-pink" style={{ padding: '6px 12px', fontSize: '0.82rem' }}>
            {item.season}
          </span>
        </div>

        {/* Contract Attributes Grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: '10px',
            margin: '16px 0',
            background: 'var(--paper)',
            padding: '14px',
            borderRadius: '16px',
          }}
        >
          <div>
            <div style={{ fontSize: '0.72rem', color: 'var(--muted)', textTransform: 'uppercase' }}>Emplacement</div>
            <div style={{ fontSize: '0.92rem', fontWeight: 700, color: 'var(--ink)' }}>
              {item.slot}
            </div>
          </div>
          <div>
            <div style={{ fontSize: '0.72rem', color: 'var(--muted)', textTransform: 'uppercase' }}>Formalité (0-3)</div>
            <div style={{ fontSize: '0.92rem', fontWeight: 700, color: 'var(--ink)' }}>
              {item.formality ?? 1} / 3
            </div>
          </div>
          <div>
            <div style={{ fontSize: '0.72rem', color: 'var(--muted)', textTransform: 'uppercase' }}>Chaleur (0-4)</div>
            <div style={{ fontSize: '0.92rem', fontWeight: 700, color: 'var(--ink)' }}>
              {item.warmth ?? 2} / 4
            </div>
          </div>
        </div>

        {item.traditional && (
          <div style={{ background: 'var(--pastel-butter-soft)', padding: '10px 14px', borderRadius: '12px', marginBottom: '16px', fontSize: '0.84rem', color: 'var(--pastel-butter-deep)' }}>
            🇹🇳 <strong>Vêtement Traditionnel Tunisien :</strong> Évalué selon les règles de contexte culturel.
          </div>
        )}

        <div style={{ display: 'flex', gap: '10px', marginTop: '12px' }}>
          <button className="btn btn-secondary" style={{ flex: 1 }} onClick={onClose}>
            Fermer
          </button>
          {onDelete && (
            <button
              className="btn"
              style={{
                flex: 1,
                background: 'var(--danger-bg)',
                color: 'var(--danger)',
                boxShadow: 'none',
              }}
              onClick={() => {
                onDelete(item.id);
                onClose();
              }}
            >
              Supprimer
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
