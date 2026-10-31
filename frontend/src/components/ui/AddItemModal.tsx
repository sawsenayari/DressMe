import { useState, useRef } from 'react';
import type { Slot, Season, ClothingItem, UsageType } from '../../types';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onAdd: (file: File, meta?: Partial<ClothingItem>) => Promise<void>;
  busy?: boolean;
}

const SLOTS: Slot[] = ['top', 'bottom', 'onepiece', 'outer', 'footwear', 'bag', 'accessory'];
const SEASONS: Season[] = ['spring', 'summer', 'autumn', 'winter', 'all'];
const USAGES: UsageType[] = ['Casual', 'Smart Casual', 'Formal', 'Sports', 'Ethnic', 'Party'];
const COLORS = ['Pink', 'Cream', 'Lavender', 'Mint', 'Butter Yellow', 'Beige', 'White', 'Black', 'Blue'];

export function AddItemModal({ isOpen, onClose, onAdd, busy }: Props) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string>('');
  const [name, setName] = useState('');
  const [slot, setSlot] = useState<Slot>('top');
  const [season, setSeason] = useState<Season>('spring');
  const [usage, setUsage] = useState<UsageType>('Casual');
  const [color, setColor] = useState('Cream');
  const [traditional, setTraditional] = useState(false);
  const [styleName, setStyleName] = useState('');
  const [error, setError] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setPreviewUrl(URL.createObjectURL(file));
      setError('');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setError('Veuillez sélectionner une photo de votre vêtement.');
      return;
    }
    try {
      await onAdd(selectedFile, {
        name: name || undefined,
        slot,
        category: slot,
        season,
        usage,
        color: color.toLowerCase(),
        colour: [color.toLowerCase()],
        traditional,
        style: styleName || undefined,
      });
      onClose();
      // Reset form
      setSelectedFile(null);
      setPreviewUrl('');
      setName('');
      setStyleName('');
      setTraditional(false);
    } catch {
      setError('Impossible d\'ajouter la pièce. Réessayez.');
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: '520px' }}>
        <button className="modal-close" onClick={onClose} aria-label="Fermer modal">
          ✕
        </button>

        <h2 style={{ marginBottom: '6px' }}>Ajouter une Pièce (ItemCard v1)</h2>
        <p style={{ color: 'var(--muted)', fontSize: '0.9rem', marginBottom: '20px' }}>
          Photo envoyée au pipeline de segmentation (SegFormer/rembg) et classificateur Qwen2.5-VL.
        </p>

        {error && (
          <div
            style={{
              padding: '10px 14px',
              borderRadius: '12px',
              background: 'var(--danger-bg)',
              color: 'var(--danger)',
              fontSize: '0.85rem',
              marginBottom: '16px',
            }}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {/* Upload Dropzone */}
          <div
            style={{
              border: '2px dashed var(--pastel-pink)',
              borderRadius: '20px',
              padding: previewUrl ? '12px' : '26px 16px',
              textAlign: 'center',
              background: 'var(--pastel-pink-subtle)',
              cursor: 'pointer',
              marginBottom: '18px',
            }}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              style={{ display: 'none' }}
              onChange={handleFileChange}
            />

            {previewUrl ? (
              <div>
                <img
                  src={previewUrl}
                  alt="Aperçu vêtement"
                  style={{
                    maxHeight: '180px',
                    width: 'auto',
                    margin: '0 auto',
                    borderRadius: '14px',
                    display: 'block',
                    boxShadow: 'var(--shadow-card)',
                  }}
                />
                <span style={{ display: 'inline-block', marginTop: '8px', fontSize: '0.78rem', color: 'var(--muted)', fontWeight: 600 }}>
                  Changer la photo
                </span>
              </div>
            ) : (
              <div>
                <div style={{ fontSize: '30px', marginBottom: '6px' }}>📸</div>
                <div style={{ fontWeight: 600, fontSize: '0.92rem', color: 'var(--ink)' }}>
                  Prendre ou importer une photo
                </div>
                <div style={{ fontSize: '0.78rem', color: 'var(--muted)', marginTop: '2px' }}>
                  Photo portée (SegFormer B2) ou à plat (rembg)
                </div>
              </div>
            )}
          </div>

          {/* Name Field */}
          <div className="form-group" style={{ marginBottom: '14px' }}>
            <label className="form-label">Nom de la pièce (optionnel)</label>
            <input
              type="text"
              className="form-input"
              placeholder="ex: Veste en jean bleue, Jebba brodée..."
              value={name}
              onChange={e => setName(e.target.value)}
            />
          </div>

          {/* Slot (Emplacement parmi les 7 officiels) */}
          <div className="form-group" style={{ marginBottom: '14px' }}>
            <label className="form-label">Emplacement (7 slots communs)</label>
            <div className="chips" style={{ marginBottom: 0 }}>
              {SLOTS.map(s => (
                <button
                  type="button"
                  key={s}
                  className="chip"
                  aria-pressed={slot === s}
                  onClick={() => setSlot(s)}
                  style={{ fontSize: '0.8rem', padding: '6px 14px' }}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          {/* Usage / Formalité */}
          <div className="form-group" style={{ marginBottom: '14px' }}>
            <label className="form-label">Usage / Occasion d'usage</label>
            <select className="form-select" value={usage} onChange={e => setUsage(e.target.value as any)}>
              {USAGES.map(u => (
                <option key={u} value={u}>
                  {u}
                </option>
              ))}
            </select>
          </div>

          {/* Season & Color */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px', marginBottom: '14px' }}>
            <div>
              <label className="form-label">Saison</label>
              <select className="form-select" value={season} onChange={e => setSeason(e.target.value as any)}>
                {SEASONS.map(s => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="form-label">Couleur Principale</label>
              <select className="form-select" value={color} onChange={e => setColor(e.target.value)}>
                {COLORS.map(c => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Traditional Garment Checkbox (Tunisian pieces support) */}
          <div style={{ marginBottom: '20px', background: 'var(--paper)', padding: '12px 14px', borderRadius: '14px', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <input
              type="checkbox"
              id="traditional-check"
              checked={traditional}
              onChange={e => setTraditional(e.target.checked)}
              style={{ width: '18px', height: '18px', accentColor: 'var(--pastel-pink-deep)' }}
            />
            <label htmlFor="traditional-check" style={{ fontSize: '0.88rem', fontWeight: 600, color: 'var(--ink)', cursor: 'pointer' }}>
              🇹🇳 Vêtement traditionnel tunisien (Jebba, Fouta, Kaftan...)
            </label>
          </div>

          {/* Submit Actions */}
          <div style={{ display: 'flex', gap: '12px' }}>
            <button
              type="button"
              className="btn btn-secondary"
              style={{ flex: 1 }}
              onClick={onClose}
              disabled={busy}
            >
              Annuler
            </button>
            <button
              type="submit"
              className="btn"
              style={{ flex: 1 }}
              disabled={busy || !selectedFile}
            >
              {busy ? 'Classification en cours…' : 'Enregistrer dans le Dressing'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
