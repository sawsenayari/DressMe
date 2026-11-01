import { useEffect, useState } from 'react';
import { useAsync } from '../hooks/useAsync';
import { getProfile, getStyleSuggestions, saveAxis } from '../services/profile';
import type { Gender, Slot, StyleAxis, StyleProfile } from '../types';
import { colourLabel, slotLabel, typeLabel, usageLabel } from '../components/ui/ItemFields';
import { useApp } from '../context/AppContext';

const AXES: { id: StyleAxis; title: string; text: string; icon: string; bonus: string }[] = [
  { id: 'efficiency', title: 'Efficacité', icon: '⚡', text: "S'habiller vite, avec des pièces faciles à combiner.",
    bonus: 'Suggestions : couleurs neutres et basiques en priorité.' },
  { id: 'economy', title: 'Économie', icon: '🌿', text: "Rentabiliser ses pièces, n'acheter que l'essentiel.",
    bonus: 'Suggestions : les moins chères en priorité (prix nécessaires).' },
  { id: 'brand', title: 'Image', icon: '💎', text: 'Affirmer un style marquant et cohérent.',
    bonus: 'Suggestions : pièces de votre style dominant en priorité.' },
  { id: 'mixte', title: 'Équilibre', icon: '⚖️', text: 'Un peu de tout : les deux points forts de votre garde-robe.',
    bonus: 'Suggestions : les deux meilleurs critères, à parts égales.' },
];
const AXIS_TITLE: Record<string, string> = Object.fromEntries(AXES.map(a => [a.id, a.title]));
const FORMALITY = ['Décontracté', 'Quotidien soigné', 'Professionnel', 'Très habillé'];
const SLOTS: Slot[] = ['top', 'bottom', 'onepiece', 'outer', 'footwear', 'bag', 'accessory'];
const SWATCH: Record<string, string> = {
  black: '#222', white: '#fafafa', grey: '#9a9a9a', beige: '#e8d8b9', brown: '#8b5a2b', blue: '#4a7bd0', red: '#d9443a',
  pink: '#f4a6c0', purple: '#9b6fd0', orange: '#f39a3b', yellow: '#f2d14b', green: '#5aa469', metallic: '#c9b37e',
  multicolor: 'conic-gradient(#d9443a, #f2d14b, #5aa469, #4a7bd0, #9b6fd0, #d9443a)',
};
const swatch = (c: string) => (c.startsWith('#') ? c : SWATCH[c.toLowerCase()] || '#ccc');

// « bottom · Casual · black/beige » (Obj5) -> « Bas · décontracté · noir et beige »
const STYLE_WORDS: Record<string, string> = {
  top: 'hauts', bottom: 'bas', onepiece: 'robes', outer: 'vestes', footwear: 'chaussures', bag: 'sacs', accessory: 'accessoires',
  casual: 'décontracté', 'smart casual': 'smart casual', formal: 'habillé', sports: 'sport', ethnic: 'traditionnel', party: 'soirée',
  black: 'noir', white: 'blanc', grey: 'gris', beige: 'beige', brown: 'marron', blue: 'bleu', red: 'rouge', pink: 'rose',
  purple: 'violet', orange: 'orange', yellow: 'jaune', green: 'vert', metallic: 'doré / argenté', multicolor: 'multicolore',
};
const styleLabel = (c?: string) => {
  if (!c) return '';
  const words = Array.from(new Set(c.split('·').map(w => w.trim()).filter(Boolean)
    .map(w => w.split('/').map(x => STYLE_WORDS[x.trim().toLowerCase()] || x.trim()).join(' et '))));
  return words.join(' · ').replace(/^./, x => x.toUpperCase());
};

const bar = (value: number, color: string) => (
  <div style={{ width: '100%', height: '8px', background: '#FFFFFF', borderRadius: '999px', margin: '10px 0 8px', overflow: 'hidden' }}>
    <div style={{ width: `${Math.max(0, Math.min(100, value))}%`, height: '100%', background: color, borderRadius: '999px' }} />
  </div>
);
const h3 = { fontSize: '1.2rem', marginBottom: '8px' } as const;
const sub = { color: 'var(--muted)', fontSize: '0.88rem', margin: '0 0 14px' } as const;

export default function Profile() {
  const { profile: contextProfile, setProfile: setContextProfile, useDemoData } = useApp();
  const [reload, setReload] = useState(0);
  const state = useAsync(() => (useDemoData ? Promise.resolve(contextProfile) : getProfile()), [useDemoData, reload]);
  const [profile, setProfile] = useState<StyleProfile>(contextProfile);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');
  const [slot, setSlot] = useState<Slot | ''>('');
  const [gender, setGender] = useState<Gender | ''>('');

  // uniquement quand un nouveau profil arrive (setContextProfile change à chaque rendu du contexte)
  useEffect(() => {
    if (state.data && !useDemoData) { setProfile(state.data); setContextProfile(state.data); }
  }, [state.data]);   // eslint-disable-line react-hooks/exhaustive-deps

  const sugg = useAsync(
    () => (useDemoData ? Promise.resolve(null) : getStyleSuggestions(slot || undefined, gender || undefined)),
    [useDemoData, slot, gender, profile.axis, profile.axisChosen],
  );

  async function chooseAxis(axis: StyleAxis | 'auto') {
    if (useDemoData) { setProfile(p => ({ ...p, axis: axis === 'auto' ? p.axis : axis })); return; }
    setSaving(true); setMsg('');
    try {
      const p = await saveAxis(axis);
      setProfile(p); setContextProfile(p);
      setMsg(axis === 'auto' ? `Orientation automatique : ${AXIS_TITLE[p.axis]}.` : `Orientation enregistrée : ${AXIS_TITLE[axis]}.`);
    } catch (e) {
      setMsg(`Choix non enregistré : ${e instanceof Error ? e.message : e}`);
    } finally { setSaving(false); }
  }

  const scores = profile.scores;
  const pct = (v?: number | null) => (v == null ? '—' : `${v} %`);
  const formality = profile.formalityPref;
  const slots = Object.entries(profile.slotCounts ?? {}).sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0));
  const maxSlot = Math.max(1, ...slots.map(([, n]) => n ?? 0));
  const live = !useDemoData;

  return (
    <>
      <header className="page-head">
        <div>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            Mon profil de style <span style={{ fontSize: '1.6rem' }}>🪞</span>
          </h1>
          <p className="page-subtitle">Ce que votre garde-robe dit de votre style, et des pièces pour le prolonger.</p>
        </div>
        {live && (
          <button className="btn-sm btn-secondary" style={{ borderRadius: '999px' }} onClick={() => setReload(r => r + 1)} disabled={state.loading}>
            {state.loading ? 'Analyse…' : '↻ Recalculer'}
          </button>
        )}
      </header>

      {live && state.error && (
        <div role="alert" style={{ background: 'var(--danger-bg)', color: 'var(--danger)', padding: '12px 18px', borderRadius: '16px', marginBottom: '20px', fontSize: '0.9rem' }}>
          Profil indisponible : {state.error.message}
        </div>
      )}
      {live && state.loading && !state.data && <p role="status" style={sub}>Analyse de votre garde-robe…</p>}

      {(live ? state.data : true) && (
        <>
          {/* Notes de l'analyse */}
          {live && (profile.model === 'référence' || !!profile.notes?.length) && (
            <div role="status" className="card card-butter" style={{ marginBottom: '20px', padding: '12px 18px' }}>
              <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '0.88rem', lineHeight: 1.6 }}>
                {profile.model === 'référence' && <li>Profil provisoire : il deviendra plus personnel à partir de 18 pièces.</li>}
                {profile.notes?.map(n => <li key={n}>{n}</li>)}
              </ul>
            </div>
          )}

          {/* Résumé */}
          <section className="card" style={{ marginBottom: '28px', background: 'linear-gradient(135deg, #FFFFFF 0%, var(--pastel-pink-subtle) 100%)', padding: '22px' }}>
            <p style={{ color: 'var(--muted)', fontSize: '0.9rem', margin: 0 }}>Votre style dominant</p>
            <h2 style={{ fontSize: '1.4rem', margin: '4px 0 2px' }}>{styleLabel(profile.dominantCluster) || 'à découvrir'}</h2>
            {profile.dominantShare != null && (
              <p style={{ color: 'var(--muted)', fontSize: '0.85rem', margin: 0 }}>{profile.dominantShare} % de vos pièces sont dans ce style</p>
            )}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px', marginTop: '16px' }}>
              {[
                { v: pct(profile.diversityScore), l: 'Variété de la garde-robe' },
                { v: formality == null ? '—' : `${formality.toFixed(1)} / 3`, l: `Formalité : ${formality == null ? '—' : FORMALITY[Math.round(formality)]}` },
                { v: profile.persona ? AXIS_TITLE[profile.persona] : AXIS_TITLE[profile.axis], l: 'Orientation calculée' },
                ...(live && profile.nItems != null ? [{ v: `${profile.nItemsUsed} / ${profile.nItems}`, l: 'Pièces analysées' }] : []),
              ].map(x => (
                <div key={x.l} style={{ background: '#FFFFFF', padding: '12px 16px', borderRadius: '16px', border: '1px solid var(--line)', textAlign: 'center' }}>
                  <div style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--pastel-mint-deep)' }}>{x.v}</div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--muted)', textTransform: 'uppercase', fontWeight: 700 }}>{x.l}</div>
                </div>
              ))}
            </div>
            {live && profile.space && (
              <p style={{ color: 'var(--muted)', fontSize: '0.78rem', margin: '12px 0 0' }}>
                Analyse faite à partir {profile.space === 'photos' ? 'des photos de vos pièces' : 'des caractéristiques de vos pièces (photos non analysées)'}.
              </p>
            )}
          </section>

          {/* Scores */}
          <section style={{ marginBottom: '28px' }}>
            <h3 style={h3}>Vos trois scores</h3>
            <p style={sub}>Calculés sur votre garde-robe ; le plus élevé donne l'orientation calculée.</p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
              {([
                ['efficacite', '⚡ Efficacité', 'card-mint', 'var(--pastel-mint-deep)', 'Couleurs neutres, basiques, peu de dispersion.'],
                ['economie', '🌿 Économie', 'card-butter', 'var(--pastel-butter-deep)',
                  profile.pricePercentile != null ? `Prix médian au ${profile.pricePercentile}e percentile du catalogue.` : 'Nécessite le prix de vos pièces.'],
                ['image', '💎 Image', 'card-lavender', 'var(--pastel-lavender-deep)', 'Style dominant marqué, formalité, couleurs fortes.'],
              ] as const).map(([k, title, cls, color, text]) => (
                <div key={k} className={`card ${cls}`} style={{ padding: '18px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: 700, fontSize: '0.9rem', color }}>{title}</span>
                    <strong style={{ fontSize: '1.3rem' }}>{pct(scores?.[k])}</strong>
                  </div>
                  {bar(scores?.[k] ?? 0, color)}
                  <p style={{ fontSize: '0.78rem', color: 'var(--muted)', margin: 0 }}>{text}</p>
                </div>
              ))}
            </div>
          </section>

          {/* Palette et répartition */}
          <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginBottom: '28px' }}>
            <div className="card" style={{ background: '#FFFFFF' }}>
              <h3 style={h3}>🎨 Votre palette</h3>
              {profile.palette?.length ? (
                <div style={{ display: 'grid', gap: '8px' }}>
                  {profile.palette.map(p => (
                    <div key={p.color} style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.88rem' }}>
                      <span aria-hidden style={{ width: '22px', height: '22px', borderRadius: '50%', background: swatch(p.color), border: '1px solid var(--line)', flex: 'none' }} />
                      <span style={{ width: '110px' }}>{p.color.startsWith('#') ? p.color : colourLabel(p.color)}</span>
                      <div style={{ flex: 1 }}>{bar(p.weight * 100, 'var(--pastel-pink-deep)')}</div>
                      <strong style={{ width: '42px', textAlign: 'right' }}>{Math.round(p.weight * 100)} %</strong>
                    </div>
                  ))}
                </div>
              ) : <p style={sub}>Palette non disponible.</p>}
            </div>
            {live && (
              <div className="card" style={{ background: '#FFFFFF' }}>
                <h3 style={h3}>👚 Pièces par catégorie</h3>
                {slots.length ? (
                  <div style={{ display: 'grid', gap: '8px' }}>
                    {slots.map(([s, n]) => (
                      <div key={s} style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.88rem' }}>
                        <span style={{ width: '120px' }}>{slotLabel(s)}</span>
                        <div style={{ flex: 1 }}>{bar(((n ?? 0) / maxSlot) * 100, 'var(--pastel-lavender-deep)')}</div>
                        <strong style={{ width: '28px', textAlign: 'right' }}>{n}</strong>
                      </div>
                    ))}
                  </div>
                ) : <p style={sub}>Aucune pièce analysée.</p>}
              </div>
            )}
          </section>

          {/* Orientation prioritaire */}
          <section style={{ marginBottom: '28px' }}>
            <h3 style={h3}>Orientation prioritaire</h3>
            <p style={sub}>
              Elle décide de l'ordre des pièces suggérées ci-dessous.{' '}
              {live && (profile.axisChosen
                ? <>Votre choix : <strong>{AXIS_TITLE[profile.axis]}</strong>.{' '}
                    <button className="btn-sm btn-secondary" style={{ borderRadius: '999px', fontSize: '0.76rem' }} disabled={saving} onClick={() => chooseAxis('auto')}>
                      Revenir à l'orientation calculée ({AXIS_TITLE[profile.persona ?? 'mixte']})
                    </button></>
                : <>Actuellement : <strong>{AXIS_TITLE[profile.axis]}</strong> (calculée d'après votre garde-robe).</>)}
            </p>
            <div className="options" style={{ marginTop: 0 }}>
              {AXES.map(a => {
                const on = profile.axis === a.id;
                return (
                  <button key={a.id} className="option" aria-pressed={on} disabled={saving} onClick={() => chooseAxis(a.id)}>
                    <div className="option-icon" style={{ background: on ? 'var(--pastel-pink-soft)' : 'var(--paper)', color: on ? 'var(--pastel-pink-deep)' : 'var(--ink)' }}>
                      {a.icon}
                    </div>
                    <h3 style={{ fontSize: '1.1rem', color: 'var(--ink)' }}>{a.title}</h3>
                    <p>{a.text}</p>
                    <p style={{ fontSize: '0.76rem', color: 'var(--muted)', marginTop: '6px' }}>{a.bonus}</p>
                  </button>
                );
              })}
            </div>
            {msg && <p role="status" style={{ fontSize: '0.85rem', color: 'var(--muted)', marginTop: '10px' }}>{msg}</p>}
          </section>

          {/* Suggestions de l'Obj5 */}
          {live && (
            <section style={{ marginBottom: '28px' }}>
              <h3 style={h3}>🛍️ Pièces qui prolongent votre style</h3>
              <p style={sub}>Choisies dans un catalogue de référence, proches de votre garde-robe et classées selon votre orientation.</p>
              <div className="chips" role="group" aria-label="Catégorie">
                <button className="chip" aria-pressed={slot === ''} onClick={() => setSlot('')}>Toutes</button>
                {SLOTS.map(s => <button key={s} className="chip" aria-pressed={slot === s} onClick={() => setSlot(s)}>{slotLabel(s)}</button>)}
              </div>
              <div className="chips" role="group" aria-label="Pour">
                {([['', 'Automatique'], ['Women', '👩 Femme'], ['Men', '👨 Homme']] as const).map(([g, l]) => (
                  <button key={g} className="chip" style={{ fontSize: '0.8rem' }} aria-pressed={gender === g} onClick={() => setGender(g)}>{l}</button>
                ))}
              </div>
              {sugg.loading && <p role="status" style={sub}>Recherche de pièces…</p>}
              {sugg.error && <p role="alert" style={{ ...sub, color: 'var(--danger)' }}>Suggestions indisponibles : {sugg.error.message}</p>}
              {sugg.data && (sugg.data.items.length ? (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '12px' }}>
                  {sugg.data.items.map(it => (
                    <article key={it.id} className="card" style={{ background: '#FFFFFF', padding: '14px 16px', display: 'grid', gap: '6px', alignContent: 'start' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        {it.colour.map(c => <span key={c} aria-hidden title={colourLabel(c)} style={{ width: '18px', height: '18px', borderRadius: '50%', background: swatch(c), border: '1px solid var(--line)' }} />)}
                        <strong style={{ fontSize: '0.95rem' }}>{it.name || typeLabel(it.type)}</strong>
                      </div>
                      <span style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>
                        {slotLabel(it.slot)} · {typeLabel(it.type)} · {it.colour.map(colourLabel).join(' + ')}{it.usage ? ` · ${usageLabel(it.usage)}` : ''}
                      </span>
                      <span style={{ fontSize: '0.82rem' }}>Proche de votre style : <strong>{it.match} %</strong></span>
                      {it.reasons.length > 0 && <span style={{ fontSize: '0.78rem', color: 'var(--pastel-mint-deep)' }}>✓ {it.reasons.join(' · ')}</span>}
                    </article>
                  ))}
                </div>
              ) : <p style={sub}>Aucune pièce à suggérer pour ce choix.</p>)}
            </section>
          )}
        </>
      )}
    </>
  );
}
