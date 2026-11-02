import { useRef, useState } from 'react';
import type { ClothingItem } from '../../types';
import type { CropPart, CropResult, ItemPatch } from '../../services/wardrobe';
import { ItemFields, formFromItem, patchFromForm, type ItemForm } from './ItemFields';

type Crop = { image: Blob; slot?: string | null };

interface Props {
  isOpen: boolean;
  onClose: () => void;
  /** Analyse la photo (reconnaissance automatique) et crée la pièce ; crop = pièce découpée choisie. */
  onAnalyze: (file: File, crop?: Crop) => Promise<ClothingItem>;
  /** Améliore la photo avant l'analyse (découpage de l'objectif 6) ; absent en mode démonstration. */
  onCrop?: (file: File) => Promise<CropResult>;
  /** Enregistre les caractéristiques vérifiées / corrigées par l'utilisateur. */
  onConfirm: (id: string, patch: ItemPatch) => Promise<unknown>;
  /** Annulation après analyse : la pièce créée est retirée. */
  onDiscard: (id: string) => Promise<unknown>;
}

// photo -> ready (rien n'est envoyé tant que l'utilisateur ne clique pas) -> [improving -> choose] -> analysing -> review
type Step = 'photo' | 'ready' | 'improving' | 'choose' | 'analysing' | 'review' | 'saving';
const ORIGINAL = -1;

const toBlob = async (dataUrl: string) => (await fetch(dataUrl)).blob();

export function AddItemModal({ isOpen, onClose, onAnalyze, onCrop, onConfirm, onDiscard }: Props) {
  const [step, setStep] = useState<Step>('photo');
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState('');
  const [crop, setCrop] = useState<CropResult | null>(null);
  const [choice, setChoice] = useState(0);
  const [item, setItem] = useState<ClothingItem | null>(null);
  const [form, setForm] = useState<ItemForm | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const reset = () => {
    setStep('photo'); setFile(null); setPreviewUrl(''); setCrop(null); setChoice(0); setItem(null); setForm(null); setError(''); setNotice('');
  };
  const close = () => { reset(); onClose(); };
  const busy = step === 'improving' || step === 'analysing' || step === 'saving';

  // 1) photo choisie : simple aperçu, rien n'est envoyé au serveur
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    e.target.value = '';
    if (!f) return;
    setFile(f); setPreviewUrl(URL.createObjectURL(f)); setError(''); setNotice(''); setCrop(null); setChoice(0); setStep('ready');
  };

  // 2a) « Améliorer la photo » (sur demande) : découpage de l'objectif 6
  const improve = async () => {
    if (!file || !onCrop) return;
    setStep('improving'); setError(''); setNotice('');
    try {
      const r = await onCrop(file);
      if (r.needed && r.parts.length) { setCrop(r); setChoice(0); setStep('choose'); return; }
      setNotice('Cette photo est déjà nette (fond clair et uni) : rien à améliorer, vous pouvez l\'analyser telle quelle.');
    } catch (err) {
      setError(`Amélioration impossible : ${err instanceof Error ? err.message : err}. Vous pouvez analyser la photo telle quelle.`);
    }
    setStep('ready');
  };

  // 2b) « Analyser » (sur demande) : photo d'origine ou pièce découpée choisie
  const analyse = async (part?: CropPart) => {
    if (!file) return;
    setStep('analysing'); setError(''); setNotice('');
    try {
      const created = await onAnalyze(file, part ? { image: await toBlob(part.image), slot: part.slot } : undefined);
      setItem(created); setForm(formFromItem(created)); setStep('review');
    } catch (err) {
      setError(`La photo n'a pas pu être analysée : ${err instanceof Error ? err.message : err}`);
      setStep(crop?.needed ? 'choose' : 'ready');
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
  const chosen = crop && choice !== ORIGINAL ? crop.parts[choice] : undefined;
  const subtitle = step === 'review' || step === 'saving'
    ? 'Voici ce que nous avons reconnu sur la photo. Vérifiez et corrigez si besoin, puis enregistrez.'
    : step === 'choose'
      ? crop?.kind === 'portée'
        ? 'Plusieurs vêtements sont visibles : choisissez celui à ajouter (vous pourrez ajouter les autres ensuite avec la même photo).'
        : 'Le fond de la photo a été retiré pour mieux reconnaître le vêtement. Gardez la version qui vous convient.'
      : step === 'ready' || step === 'improving' || step === 'analysing'
        ? `Rien n'est envoyé sans votre accord : ${onCrop ? 'améliorez la photo si besoin (fond chargé, photo portée), puis ' : ''}lancez l'analyse.`
        : 'Choisissez une photo : vous pourrez l\'améliorer puis lancer la reconnaissance du vêtement, qui remplit sa fiche pour vous.';

  const tile = (idx: number, src: string, label: string) => (
    <button key={idx} type="button" onClick={() => setChoice(idx)} aria-pressed={choice === idx}
            style={{ border: choice === idx ? '2px solid var(--pastel-pink-deep)' : '1px solid var(--line)', borderRadius: '14px',
                     background: '#FFFFFF', padding: '8px', cursor: 'pointer', display: 'grid', gap: '6px', justifyItems: 'center' }}>
      <img src={src} alt={label} style={{ height: '120px', maxWidth: '100%', objectFit: 'contain' }} />
      <span style={{ fontSize: '0.8rem', fontWeight: choice === idx ? 700 : 500 }}>{choice === idx ? '✓ ' : ''}{label}</span>
    </button>
  );

  return (
    <div className="modal-backdrop" onClick={step === 'photo' ? close : undefined}>
      <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: '600px', maxHeight: '92vh', overflowY: 'auto' }}>
        <button className="modal-close" onClick={cancel} aria-label="Fermer" disabled={busy}>✕</button>

        <h2 style={{ marginBottom: '6px' }}>Ajouter une pièce</h2>
        <p style={{ color: 'var(--muted)', fontSize: '0.88rem', marginBottom: '18px' }}>{subtitle}</p>

        {error && (
          <div role="alert" style={{ padding: '10px 14px', borderRadius: '12px', background: 'var(--danger-bg)', color: 'var(--danger)', fontSize: '0.85rem', marginBottom: '16px' }}>
            {error}
          </div>
        )}
        {notice && (
          <div role="status" style={{ padding: '10px 14px', borderRadius: '12px', background: 'var(--pastel-mint-soft, #e8f7f1)', fontSize: '0.85rem', marginBottom: '16px' }}>
            {notice}
          </div>
        )}

        {step === 'choose' && crop ? (
          <div role="group" aria-label="Choix de la photo" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: '10px', marginBottom: '18px' }}>
            {crop.parts.map((p, i) => tile(i, p.image, p.label))}
            {tile(ORIGINAL, previewUrl, "Photo d'origine")}
          </div>
        ) : (
          <div
            style={{ border: '2px dashed var(--pastel-pink)', borderRadius: '20px', padding: previewUrl ? '12px' : '26px 16px', textAlign: 'center',
                     background: 'var(--pastel-pink-subtle)', cursor: step === 'photo' || step === 'ready' ? 'pointer' : 'default', marginBottom: '18px' }}
            onClick={() => (step === 'photo' || step === 'ready') && fileInputRef.current?.click()}
          >
            {previewUrl ? (
              <div>
                <img src={item?.imageCrop || chosen?.image || previewUrl} alt="Aperçu du vêtement"
                     style={{ maxHeight: '170px', width: 'auto', margin: '0 auto', borderRadius: '14px', display: 'block', boxShadow: 'var(--shadow-card)' }} />
                <span style={{ display: 'inline-block', marginTop: '8px', fontSize: '0.8rem', color: 'var(--muted)', fontWeight: 600 }}>
                  {step === 'improving' ? '✂️ Amélioration de la photo… (quelques secondes)'
                    : step === 'analysing' ? '🔎 Analyse de la photo… (quelques secondes)'
                    : step === 'photo' || step === 'ready' ? 'Changer la photo' : '✓ Photo analysée'}
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
        )}
        <input ref={fileInputRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={handleFileChange} />

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
          <button type="button" className="btn btn-secondary" style={{ flex: 1 }} onClick={cancel} disabled={busy}>
            Annuler
          </button>
          {step === 'photo' && (
            <button type="button" className="btn" style={{ flex: 1 }} onClick={() => fileInputRef.current?.click()}>Choisir une photo</button>
          )}
          {step === 'ready' && onCrop && (
            <button type="button" className="btn btn-secondary" style={{ flex: 1 }} onClick={improve}>✂️ Améliorer la photo</button>
          )}
          {step === 'ready' && (
            <button type="button" className="btn" style={{ flex: 1 }} onClick={() => analyse()}>🔎 Analyser la photo</button>
          )}
          {step === 'choose' && file && (
            <button type="button" className="btn" style={{ flex: 1 }} onClick={() => analyse(chosen)}>
              {chosen ? `Analyser : ${chosen.label.toLowerCase()}` : "Analyser la photo d'origine"}
            </button>
          )}
          {(step === 'improving' || step === 'analysing') && (
            <button type="button" className="btn" style={{ flex: 1 }} disabled>{step === 'improving' ? 'Amélioration…' : 'Analyse en cours…'}</button>
          )}
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
