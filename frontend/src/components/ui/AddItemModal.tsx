import { useRef, useState } from 'react';
import type { ClothingItem } from '../../types';
import type { ItemPatch } from '../../services/wardrobe';
import { ItemFields, formFromItem, patchFromForm, type ItemForm } from './ItemFields';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  /** Analyse la photo (reconnaissance automatique) et crée la pièce ; renvoie ses caractéristiques détectées. */
  onAnalyze: (file: File) => Promise<ClothingItem>;
  /** Enregistre les caractéristiques vérifiées / corrigées par l'utilisateur. */
  onConfirm: (id: string, patch: ItemPatch) => Promise<unknown>;
  /** Annulation après analyse : la pièce créée est retirée. */
  onDiscard: (id: string) => Promise<unknown>;
}

type Step = 'photo' | 'analysing' | 'review' | 'saving';

export function AddItemModal({ isOpen, onClose, onAnalyze, onConfirm, onDiscard }: Props) {
  const [step, setStep] = useState<Step>('photo');
  const [previewUrl, setPreviewUrl] = useState('');
  const [item, setItem] = useState<ClothingItem | null>(null);
  const [form, setForm] = useState<ItemForm | null>(null);
  const [error, setError] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const reset = () => { setStep('photo'); setPreviewUrl(''); setItem(null); setForm(null); setError(''); };
  const close = () => { reset(); onClose(); };

  // 1) photo choisie -> analyse immédiate
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setPreviewUrl(URL.createObjectURL(file)); setError(''); setStep('analysing');
    try {
      const created = await onAnalyze(file);
      setItem(created); setForm(formFromItem(created)); setStep('review');
    } catch (err) {
      setError(`La photo n'a pas pu être analysée : ${err instanceof Error ? err.message : err}`);
      setStep('photo');
    }
  };

  // 3) enregistrement des caractéristiques vérifiées
  const save = async () => {
    if (!item || !form) return;
    const missing = [!form.name.trim() && 'nom', !form.slot && 'emplacement', !form.type.trim() && 'type', !form.colour1 && 'couleur principale',
                     !form.usage && 'usage', form.formality === '' && 'formalité', form.warmth === '' && 'chaleur'].filter(Boolean);
    if (missing.length) { setError(`À renseigner : ${missing.join(', ')}.`); return; }
    setStep('saving'); setError('');
    try {
      await onConfirm(item.id, patchFromForm(form, true));
      close();
    } catch (err) {
      setError(`Enregistrement impossible : ${err instanceof Error ? err.message : err}`); setStep('review');
    }
  };

  // annulation après analyse : on ne laisse pas une pièce non validée dans la garde-robe
  const cancel = async () => {
    if (item && step === 'review') {
      try { await onDiscard(item.id); } catch { /* déjà supprimée ou serveur indisponible : rien à faire */ }
    }
    close();
  };

  const lowConfidence = !!item && ((item.confidence?.slot ?? 1) < 0.75 || (item.confidence?.colour ?? 1) < 0.75);

  return (
    <div className="modal-backdrop" onClick={step === 'photo' ? close : undefined}>
      <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: '560px', maxHeight: '92vh', overflowY: 'auto' }}>
        <button className="modal-close" onClick={cancel} aria-label="Fermer" disabled={step === 'analysing' || step === 'saving'}>✕</button>

        <h2 style={{ marginBottom: '6px' }}>Ajouter une pièce</h2>
        <p style={{ color: 'var(--muted)', fontSize: '0.88rem', marginBottom: '18px' }}>
          {step === 'review' || step === 'saving'
            ? 'Voici ce que nous avons reconnu sur la photo. Vérifiez et corrigez si besoin, puis enregistrez.'
            : 'Choisissez une photo : nous reconnaissons le vêtement et remplissons sa fiche pour vous.'}
        </p>

        {error && (
          <div role="alert" style={{ padding: '10px 14px', borderRadius: '12px', background: 'var(--danger-bg)', color: 'var(--danger)', fontSize: '0.85rem', marginBottom: '16px' }}>
            {error}
          </div>
        )}

        <div
          style={{ border: '2px dashed var(--pastel-pink)', borderRadius: '20px', padding: previewUrl ? '12px' : '26px 16px', textAlign: 'center',
                   background: 'var(--pastel-pink-subtle)', cursor: step === 'photo' ? 'pointer' : 'default', marginBottom: '18px' }}
          onClick={() => step === 'photo' && fileInputRef.current?.click()}
        >
          <input ref={fileInputRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={handleFileChange} />
          {previewUrl ? (
            <div>
              <img src={item?.imageCrop || previewUrl} alt="Aperçu du vêtement"
                   style={{ maxHeight: '170px', width: 'auto', margin: '0 auto', borderRadius: '14px', display: 'block', boxShadow: 'var(--shadow-card)' }} />
              <span style={{ display: 'inline-block', marginTop: '8px', fontSize: '0.8rem', color: 'var(--muted)', fontWeight: 600 }}>
                {step === 'analysing' ? '🔎 Analyse de la photo… (quelques secondes)' : step === 'photo' ? 'Changer la photo' : '✓ Photo analysée'}
              </span>
            </div>
          ) : (
            <div>
              <div style={{ fontSize: '30px', marginBottom: '6px' }}>📸</div>
              <div style={{ fontWeight: 600, fontSize: '0.92rem', color: 'var(--ink)' }}>Prendre ou importer une photo</div>
              <div style={{ fontSize: '0.78rem', color: 'var(--muted)', marginTop: '2px' }}>Portée sur soi ou posée à plat</div>
            </div>
          )}
        </div>

        {form && (step === 'review' || step === 'saving') && (
          <>
            {lowConfidence && (
              <p style={{ background: 'var(--pastel-butter-soft)', padding: '10px 14px', borderRadius: '12px', fontSize: '0.84rem', margin: '0 0 14px' }}>
                ⚠️ La reconnaissance n'est pas sûre pour cette photo : vérifiez surtout l'emplacement et la couleur.
              </p>
            )}
            <p style={{ fontSize: '0.8rem', color: 'var(--muted)', margin: '0 0 12px' }}>
              La formalité et la chaleur sont des estimations : ajustez-les si besoin.
            </p>
            <ItemFields form={form} onChange={setForm} idPrefix="add" />
          </>
        )}

        <div style={{ display: 'flex', gap: '12px', marginTop: '20px' }}>
          <button type="button" className="btn btn-secondary" style={{ flex: 1 }} onClick={cancel} disabled={step === 'analysing' || step === 'saving'}>
            Annuler
          </button>
          {step === 'photo' && (
            <button type="button" className="btn" style={{ flex: 1 }} onClick={() => fileInputRef.current?.click()}>Choisir une photo</button>
          )}
          {step === 'analysing' && <button type="button" className="btn" style={{ flex: 1 }} disabled>Analyse en cours…</button>}
          {(step === 'review' || step === 'saving') && (
            <button type="button" className="btn" style={{ flex: 1 }} onClick={save} disabled={step === 'saving'}>
              {step === 'saving' ? 'Enregistrement…' : 'Enregistrer dans ma garde-robe'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
