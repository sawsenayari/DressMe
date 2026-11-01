import { useEffect, useState } from 'react';
import type { ClothingItem } from '../../types';
import type { ItemPatch } from '../../services/wardrobe';
import {
  FORMALITY_OPTIONS, ItemFields, WARMTH_OPTIONS, coloursLabel, formFromItem, patchFromForm, seasonLabel, slotLabel, usageLabel,
  type ItemForm,
} from './ItemFields';

interface Props {
  item: ClothingItem | null;
  onClose: () => void;
  /** Enregistre une correction (patch vide = confirmer les attributs détectés). Renvoie la fiche à jour. */
  onSave?: (id: string, patch: ItemPatch) => Promise<ClothingItem | void>;
  onDelete?: (id: string) => Promise<void> | void;
}

export function ItemDetailModal({ item, onClose, onSave, onDelete }: Props) {
  const [current, setCurrent] = useState<ClothingItem | null>(item);
  const [showCrop, setShowCrop] = useState(false);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<ItemForm | null>(item ? formFromItem(item) : null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setCurrent(item); setForm(item ? formFromItem(item) : null); setEditing(false); setError(''); setShowCrop(false);
  }, [item]);

  if (!current || !form) return null;

  const confSlot = current.confidence?.slot != null ? Math.round(current.confidence.slot * 100) : null;
  const confColour = current.confidence?.colour != null ? Math.round(current.confidence.colour * 100) : null;
  const corrected = current.source === 'user_corrected';
  const isLowConfidence = !corrected && ((confSlot ?? 100) < 75 || (confColour ?? 100) < 75);

  async function run(action: () => Promise<void>) {
    setBusy(true); setError('');
    try { await action(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  }

  const save = (patch: ItemPatch) => run(async () => {
    if (!onSave || !current) return;
    const updated = await onSave(current.id, patch);
    if (updated) { setCurrent(updated); setForm(formFromItem(updated)); }
    setEditing(false);
  });

  const submit = () => {
    const missing = [!form.name.trim() && 'nom', !form.slot && 'emplacement', !form.type.trim() && 'type', !form.colour1 && 'couleur principale',
                     !form.usage && 'usage', form.formality === '' && 'formalité', form.warmth === '' && 'chaleur'].filter(Boolean);
    if (missing.length) { setError(`À renseigner : ${missing.join(', ')}.`); return; }
    save(patchFromForm(form, true));
  };

  const remove = () => {
    if (!onDelete || !current) return;
    if (!window.confirm(`Supprimer « ${current.name || current.id} » de la garde-robe ? Cette action est définitive.`)) return;
    run(async () => { await onDelete(current.id); onClose(); });
  };

  const facts: [string, string][] = [
    ['Emplacement', slotLabel(current.slot)],
    ['Type', current.type || '—'],
    ['Couleur', coloursLabel(current)],
    ['Saison', seasonLabel(current.season)],
    ['Usage', usageLabel(current.usage)],
    ['Formalité', current.formality != null ? FORMALITY_OPTIONS[current.formality] ?? String(current.formality) : '—'],
    ['Chaleur', current.warmth != null ? WARMTH_OPTIONS[current.warmth] ?? String(current.warmth) : '—'],
    ['Source', corrected ? 'corrigée par vous' : current.source === 'obj1.knn' ? 'Obj1 (voisins)' : current.source === 'obj1.llm' ? 'Obj1 (LLM)' : current.source || '—'],
  ];

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: '540px', maxHeight: '92vh', overflowY: 'auto' }}>
        <button className="modal-close" onClick={onClose} aria-label="Fermer">✕</button>

        {/* Photo brute / découpe (Objectif 1) */}
        <div style={{ position: 'relative', width: '100%', height: editing ? '170px' : '280px', borderRadius: '20px', overflow: 'hidden', marginBottom: '16px', background: showCrop ? '#FFFFFF' : 'var(--paper)', border: '1px solid var(--line)' }}>
          <img src={showCrop ? (current.imageCrop || current.imageUrl) : current.imageUrl} alt={current.name || current.type || slotLabel(current.slot)}
               style={{ width: '100%', height: '100%', objectFit: editing ? 'contain' : 'cover' }} />
          <button onClick={() => setShowCrop(!showCrop)}
                  style={{ position: 'absolute', bottom: '10px', right: '10px', background: 'rgba(255,255,255,0.92)', padding: '6px 12px', borderRadius: '999px', fontSize: '0.76rem', fontWeight: 700, boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}>
            {showCrop ? '🖼️ Voir la photo' : '✂️ Voir la découpe'}
          </button>
        </div>

        {error && (
          <div role="alert" style={{ background: 'var(--danger-bg)', color: 'var(--danger)', padding: '10px 14px', borderRadius: '12px', marginBottom: '12px', fontSize: '0.86rem' }}>
            {error}
          </div>
        )}

        {!editing && (isLowConfidence || corrected) && (
          <div style={{ background: corrected ? 'var(--pastel-mint-soft)' : 'var(--pastel-butter-soft)', padding: '10px 14px', borderRadius: '14px', marginBottom: '16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px', fontSize: '0.84rem' }}>
            <div>
              <span style={{ fontWeight: 700 }}>{corrected ? '✓ Caractéristiques confirmées par vous' : '⚠️ Vérification recommandée'}</span>
              {!corrected && (
                <div style={{ fontSize: '0.76rem', color: 'var(--muted)' }}>
                  Confiance de l'Obj1 : emplacement {confSlot ?? '—'} %, couleur {confColour ?? '—'} %. Vérifiez, puis confirmez ou modifiez.
                </div>
              )}
            </div>
            {!corrected && onSave && (
              <button className="btn-sm btn-secondary" style={{ borderRadius: '999px', fontSize: '0.76rem' }} disabled={busy} onClick={() => save({})}>
                Confirmer
              </button>
            )}
          </div>
        )}

        {editing ? (
          <ItemFields form={form} onChange={setForm} idPrefix="edit" />
        ) : (
          <>
            <h2 style={{ fontSize: '1.35rem', marginBottom: '2px' }}>{current.name || current.type || slotLabel(current.slot)}</h2>
            <p style={{ color: 'var(--muted)', fontSize: '0.8rem', margin: '0 0 12px' }}>ID : <code>{current.id}</code></p>
            <dl style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '10px 16px', margin: '0 0 16px', background: 'var(--paper)', padding: '14px', borderRadius: '16px' }}>
              {facts.map(([k, v]) => (
                <div key={k}>
                  <dt style={{ fontSize: '0.7rem', color: 'var(--muted)', textTransform: 'uppercase' }}>{k}</dt>
                  <dd style={{ margin: 0, fontSize: '0.9rem', fontWeight: 700, color: 'var(--ink)' }}>{v}</dd>
                </div>
              ))}
            </dl>
            {current.traditional && (
              <div style={{ background: 'var(--pastel-butter-soft)', padding: '10px 14px', borderRadius: '12px', marginBottom: '16px', fontSize: '0.84rem', color: 'var(--pastel-butter-deep)' }}>
                🇹🇳 <strong>Vêtement traditionnel tunisien</strong> : évalué selon les règles de contexte culturel.
              </div>
            )}
          </>
        )}

        <div style={{ display: 'flex', gap: '10px', marginTop: '14px', flexWrap: 'wrap' }}>
          {editing ? (
            <>
              <button className="btn btn-secondary" style={{ flex: 1 }} disabled={busy} onClick={() => { setEditing(false); setForm(formFromItem(current)); setError(''); }}>Annuler</button>
              <button className="btn" style={{ flex: 1 }} disabled={busy} onClick={submit}>{busy ? 'Enregistrement…' : 'Enregistrer'}</button>
            </>
          ) : (
            <>
              <button className="btn btn-secondary" style={{ flex: 1 }} onClick={onClose}>Fermer</button>
              {onSave && <button className="btn btn-secondary" style={{ flex: 1 }} disabled={busy} onClick={() => setEditing(true)}>✏️ Modifier</button>}
              {onDelete && (
                <button className="btn" style={{ flex: 1, background: 'var(--danger-bg)', color: 'var(--danger)', boxShadow: 'none' }} disabled={busy} onClick={remove}>
                  🗑️ Supprimer
                </button>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
