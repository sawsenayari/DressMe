import { useRef, useState } from 'react';
import type { ItemPatch } from '../../services/wardrobe';
import { EMPTY_FORM, ItemFields, patchFromForm, type ItemForm } from './ItemFields';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  /** patch : caractéristiques saisies (les champs « Auto » sont laissés à la détection de l'Obj1). */
  onAdd: (file: File, patch: ItemPatch) => Promise<void>;
  busy?: boolean;
}

export function AddItemModal({ isOpen, onClose, onAdd, busy }: Props) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState('');
  const [form, setForm] = useState<ItemForm>(EMPTY_FORM);
  const [error, setError] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const reset = () => { setSelectedFile(null); setPreviewUrl(''); setForm(EMPTY_FORM); setError(''); };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) { setSelectedFile(file); setPreviewUrl(URL.createObjectURL(file)); setError(''); }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) { setError('Sélectionnez une photo du vêtement.'); return; }
    try {
      await onAdd(selectedFile, patchFromForm(form));
      reset();
      onClose();
    } catch (err) {
      setError(`Impossible d'ajouter la pièce : ${err instanceof Error ? err.message : err}`);
    }
  };

  return (
    <div className="modal-backdrop" onClick={busy ? undefined : onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: '540px', maxHeight: '92vh', overflowY: 'auto' }}>
        <button className="modal-close" onClick={onClose} aria-label="Fermer" disabled={busy}>✕</button>

        <h2 style={{ marginBottom: '6px' }}>Ajouter une pièce</h2>
        <p style={{ color: 'var(--muted)', fontSize: '0.88rem', marginBottom: '18px' }}>
          L'Objectif 1 découpe la photo et détecte les caractéristiques. Laissez « Auto » ou renseignez ce que vous connaissez :
          vos choix remplacent la détection.
        </p>

        {error && (
          <div role="alert" style={{ padding: '10px 14px', borderRadius: '12px', background: 'var(--danger-bg)', color: 'var(--danger)', fontSize: '0.85rem', marginBottom: '16px' }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div
            style={{ border: '2px dashed var(--pastel-pink)', borderRadius: '20px', padding: previewUrl ? '12px' : '26px 16px', textAlign: 'center', background: 'var(--pastel-pink-subtle)', cursor: 'pointer', marginBottom: '18px' }}
            onClick={() => fileInputRef.current?.click()}
          >
            <input ref={fileInputRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={handleFileChange} />
            {previewUrl ? (
              <div>
                <img src={previewUrl} alt="Aperçu du vêtement" style={{ maxHeight: '170px', width: 'auto', margin: '0 auto', borderRadius: '14px', display: 'block', boxShadow: 'var(--shadow-card)' }} />
                <span style={{ display: 'inline-block', marginTop: '8px', fontSize: '0.78rem', color: 'var(--muted)', fontWeight: 600 }}>Changer la photo</span>
              </div>
            ) : (
              <div>
                <div style={{ fontSize: '30px', marginBottom: '6px' }}>📸</div>
                <div style={{ fontWeight: 600, fontSize: '0.92rem', color: 'var(--ink)' }}>Prendre ou importer une photo</div>
                <div style={{ fontSize: '0.78rem', color: 'var(--muted)', marginTop: '2px' }}>Portée sur soi ou posée à plat</div>
              </div>
            )}
          </div>

          <ItemFields form={form} onChange={setForm} auto idPrefix="add" />

          <div style={{ display: 'flex', gap: '12px', marginTop: '20px' }}>
            <button type="button" className="btn btn-secondary" style={{ flex: 1 }} onClick={onClose} disabled={busy}>Annuler</button>
            <button type="submit" className="btn" style={{ flex: 1 }} disabled={busy || !selectedFile}>
              {busy ? 'Analyse en cours…' : 'Ajouter à la garde-robe'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
