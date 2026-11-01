import { useEffect, useState } from 'react';
import type { ClothingItem, Season, Slot, UsageType } from '../../types';
import type { ItemPatch } from '../../services/wardrobe';

interface Props {
  item: ClothingItem | null;
  onClose: () => void;
  /** Enregistre une correction (patch vide = confirmer les attributs détectés). Renvoie la fiche à jour. */
  onSave?: (id: string, patch: ItemPatch) => Promise<ClothingItem | void>;
  onDelete?: (id: string) => Promise<void> | void;
}

const SLOT_OPTIONS: { id: Slot; label: string }[] = [
  { id: 'top', label: 'Haut' }, { id: 'bottom', label: 'Bas' }, { id: 'onepiece', label: 'Robe / pièce unique' },
  { id: 'outer', label: 'Veste / manteau' }, { id: 'footwear', label: 'Chaussures' }, { id: 'bag', label: 'Sac' },
  { id: 'accessory', label: 'Accessoire' },
];
const SEASON_OPTIONS: { id: Season; label: string }[] = [
  { id: 'all', label: 'Toutes saisons' }, { id: 'spring', label: 'Printemps' }, { id: 'summer', label: 'Été' },
  { id: 'autumn', label: 'Automne' }, { id: 'winter', label: 'Hiver' },
];
const USAGE_OPTIONS: UsageType[] = ['Casual', 'Smart Casual', 'Formal', 'Sports', 'Ethnic', 'Party'];

type Form = {
  name: string; slot: Slot; type: string; colour1: string; colour2: string; season: Season;
  usage: UsageType; formality: number; warmth: number; traditional: boolean;
};

const toForm = (i: ClothingItem): Form => ({
  name: i.name || '', slot: i.slot, type: i.type || '', colour1: i.colour?.[0] || i.color || '', colour2: i.colour?.[1] || '',
  season: i.season || 'all', usage: i.usage || 'Casual', formality: i.formality ?? 1, warmth: i.warmth ?? 1,
  traditional: !!i.traditional,
});

const label: React.CSSProperties = { fontSize: '0.72rem', color: 'var(--muted)', textTransform: 'uppercase', display: 'block', marginBottom: '4px' };
const field: React.CSSProperties = { width: '100%', padding: '8px 10px', borderRadius: '10px', border: '1px solid var(--line)', fontSize: '0.9rem', background: '#FFFFFF' };

export function ItemDetailModal({ item, onClose, onSave, onDelete }: Props) {
  const [current, setCurrent] = useState<ClothingItem | null>(item);
  const [showCrop, setShowCrop] = useState(false);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<Form | null>(item ? toForm(item) : null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setCurrent(item); setForm(item ? toForm(item) : null); setEditing(false); setError(''); setShowCrop(false);
  }, [item]);

  if (!current || !form) return null;

  const confSlot = current.confidence?.slot != null ? Math.round(current.confidence.slot * 100) : null;
  const confColour = current.confidence?.colour != null ? Math.round(current.confidence.colour * 100) : null;
  const corrected = current.source === 'user_corrected';
  const isLowConfidence = !corrected && ((confSlot ?? 100) < 75 || (confColour ?? 100) < 75);
  const set = <K extends keyof Form>(k: K, v: Form[K]) => setForm({ ...form, [k]: v });

  async function run(action: () => Promise<void>) {
    setBusy(true); setError('');
    try { await action(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  }

  const save = (patch: ItemPatch) => run(async () => {
    if (!onSave || !current) return;
    const updated = await onSave(current.id, patch);
    if (updated) { setCurrent(updated); setForm(toForm(updated)); }
    setEditing(false);
  });

  const submit = () => {
    if (!form.name.trim() || !form.type.trim() || !form.colour1.trim()) { setError('Nom, type et couleur principale sont obligatoires.'); return; }
    save({
      name: form.name.trim(), slot: form.slot, type: form.type.trim(),
      colour: [form.colour1, form.colour2].map(c => c.trim().toLowerCase()).filter(Boolean),
      season: form.season, usage: form.usage, formality: form.formality, warmth: form.warmth, traditional: form.traditional,
    });
  };

  const remove = () => {
    if (!onDelete || !current) return;
    if (!window.confirm(`Supprimer « ${current.name || current.id} » de la garde-robe ? Cette action est définitive.`)) return;
    run(async () => { await onDelete(current.id); onClose(); });
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: '520px', maxHeight: '92vh', overflowY: 'auto' }}>
        <button className="modal-close" onClick={onClose} aria-label="Fermer">✕</button>

        {/* Photo brute / découpe (Objectif 1) */}
        <div style={{ position: 'relative', width: '100%', height: editing ? '180px' : '280px', borderRadius: '20px', overflow: 'hidden', marginBottom: '16px', background: showCrop ? '#FFFFFF' : 'var(--paper)', border: '1px solid var(--line)' }}>
          <img src={showCrop ? (current.imageCrop || current.imageUrl) : current.imageUrl} alt={current.name || current.color}
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
              <span style={{ fontWeight: 700 }}>{corrected ? '✓ Attributs confirmés par vous' : '⚠️ Vérification recommandée'}</span>
              {!corrected && (
                <div style={{ fontSize: '0.76rem', color: 'var(--muted)' }}>
                  Confiance emplacement {confSlot ?? '—'} %, couleur {confColour ?? '—'} % (source : {current.source || 'inconnue'})
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
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '8px' }}>
            <div style={{ gridColumn: '1 / -1' }}>
              <label style={label} htmlFor="f-name">Nom</label>
              <input id="f-name" style={field} value={form.name} onChange={e => set('name', e.target.value)} />
            </div>
            <div>
              <label style={label} htmlFor="f-slot">Emplacement</label>
              <select id="f-slot" style={field} value={form.slot} onChange={e => set('slot', e.target.value as Slot)}>
                {SLOT_OPTIONS.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
              </select>
            </div>
            <div>
              <label style={label} htmlFor="f-type">Type fin</label>
              <input id="f-type" style={field} value={form.type} onChange={e => set('type', e.target.value)} placeholder="ex. Jeans, Blazers" />
            </div>
            <div>
              <label style={label} htmlFor="f-c1">Couleur principale</label>
              <input id="f-c1" style={field} value={form.colour1} onChange={e => set('colour1', e.target.value)} placeholder="ex. black" />
            </div>
            <div>
              <label style={label} htmlFor="f-c2">Couleur secondaire</label>
              <input id="f-c2" style={field} value={form.colour2} onChange={e => set('colour2', e.target.value)} placeholder="facultatif" />
            </div>
            <div>
              <label style={label} htmlFor="f-season">Saison</label>
              <select id="f-season" style={field} value={form.season} onChange={e => set('season', e.target.value as Season)}>
                {SEASON_OPTIONS.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
              </select>
            </div>
            <div>
              <label style={label} htmlFor="f-usage">Usage</label>
              <select id="f-usage" style={field} value={form.usage} onChange={e => set('usage', e.target.value as UsageType)}>
                {USAGE_OPTIONS.map(u => <option key={u} value={u}>{u}</option>)}
              </select>
            </div>
            <div>
              <label style={label} htmlFor="f-form">Formalité (0-3) : {form.formality}</label>
              <input id="f-form" type="range" min={0} max={3} step={1} style={{ width: '100%' }} value={form.formality} onChange={e => set('formality', Number(e.target.value))} />
            </div>
            <div>
              <label style={label} htmlFor="f-warm">Chaleur (0-4) : {form.warmth}</label>
              <input id="f-warm" type="range" min={0} max={4} step={1} style={{ width: '100%' }} value={form.warmth} onChange={e => set('warmth', Number(e.target.value))} />
            </div>
            <label style={{ gridColumn: '1 / -1', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.88rem' }}>
              <input type="checkbox" checked={form.traditional} onChange={e => set('traditional', e.target.checked)} />
              Pièce traditionnelle tunisienne (jebba, kachabia, fouta…)
            </label>
          </div>
        ) : (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
              <div>
                <h2 style={{ textTransform: 'capitalize', fontSize: '1.35rem' }}>{current.name || `${current.color} ${current.slot}`}</h2>
                <p style={{ color: 'var(--muted)', fontSize: '0.88rem', margin: '4px 0 0' }}>
                  ID : <code>{current.id}</code> • Type : <strong>{current.type || current.slot}</strong> • Couleur : <strong>{(current.colour || [current.color]).join(', ')}</strong>
                </p>
              </div>
              <span className="chip-tag chip-tag-pink" style={{ padding: '6px 12px', fontSize: '0.82rem' }}>{current.season}</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px', margin: '16px 0', background: 'var(--paper)', padding: '14px', borderRadius: '16px' }}>
              {[['Emplacement', current.slot], ['Usage', current.usage || '—'], ['Formalité', `${current.formality ?? '—'} / 3`], ['Chaleur', `${current.warmth ?? '—'} / 4`]].map(([k, v]) => (
                <div key={k}>
                  <div style={{ fontSize: '0.72rem', color: 'var(--muted)', textTransform: 'uppercase' }}>{k}</div>
                  <div style={{ fontSize: '0.92rem', fontWeight: 700, color: 'var(--ink)' }}>{v}</div>
                </div>
              ))}
            </div>
            {current.traditional && (
              <div style={{ background: 'var(--pastel-butter-soft)', padding: '10px 14px', borderRadius: '12px', marginBottom: '16px', fontSize: '0.84rem', color: 'var(--pastel-butter-deep)' }}>
                🇹🇳 <strong>Vêtement traditionnel tunisien</strong> : évalué selon les règles de contexte culturel.
              </div>
            )}
          </>
        )}

        <div style={{ display: 'flex', gap: '10px', marginTop: '12px', flexWrap: 'wrap' }}>
          {editing ? (
            <>
              <button className="btn btn-secondary" style={{ flex: 1 }} disabled={busy} onClick={() => { setEditing(false); setForm(toForm(current)); setError(''); }}>Annuler</button>
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
