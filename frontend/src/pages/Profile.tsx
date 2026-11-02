import { useEffect, useState } from 'react';
import { useAsync } from '../hooks/useAsync';
import { getProfile, getStyleSuggestions } from '../services/profile';
import type { Gender, Slot, StyleProfile } from '../types';
import { colourLabel, slotLabel, typeLabel, usageLabel } from '../components/ui/ItemFields';
import { useApp } from '../context/AppContext';

// orientation calculée par l'Obj5 (persona)
const AXIS_TITLE: Record<string, string> = { efficiency: 'Efficacité', brand: 'Image', mixte: 'Équilibre' };
const axisOf = (p: StyleProfile) => { const a = p.persona ?? p.axis; return a in AXIS_TITLE ? a : 'mixte'; };
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

// Bilan : une ligne par thème (icône, titre, valeur forte, détail), tiré des résultats de l'Obj5
const PERSONA_TEXT: Record<string, string> = {
  efficiency: 'beaucoup de couleurs neutres et de pièces basiques : des tenues faciles et rapides à composer',
  brand: 'un style marqué et cohérent, avec des pièces habillées ou des couleurs fortes',
  mixte: 'un équilibre entre pièces pratiques et pièces qui affirment votre style',
};
type BilanRow = { icon: string; title: string; value: string; detail?: string; swatches?: string[]; warn?: boolean };
function bilan(p: StyleProfile): BilanRow[] {
  const rows: BilanRow[] = [];
  const slots = Object.entries(p.slotCounts ?? {}).sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0));
  if (p.nItems != null)
    rows.push({ icon: '👚', title: 'Garde-robe', value: `${p.nItems} pièces`,
                detail: slots.length ? `surtout des ${STYLE_WORDS[slots[0][0]] ?? slots[0][0]} (${slots[0][1]})` : undefined });
  const pal = (p.palette ?? []).slice(0, 3);
  if (pal.length)
    rows.push({ icon: '🎨', title: 'Couleurs', value: pal.slice(0, 2).map(c => colourLabel(c.color).toLowerCase()).join(' et '),
                detail: 'les plus présentes', swatches: pal.map(c => c.color) });
  if (p.diversityScore != null)
    rows.push({ icon: '🧩', title: 'Variété', value: p.diversityScore >= 70 ? 'variée' : p.diversityScore >= 40 ? 'assez variée' : 'peu variée',
                detail: `${p.diversityScore} % : vos pièces se répartissent entre plusieurs styles` });
  if (p.formalityPref != null)
    rows.push({ icon: '👔', title: 'Style', value: FORMALITY[Math.round(p.formalityPref)].toLowerCase(),
                detail: `formalité moyenne ${p.formalityPref.toFixed(1)} sur 3` });
  const axis = axisOf(p);
  rows.push({ icon: '🧭', title: 'Orientation', value: AXIS_TITLE[axis], detail: PERSONA_TEXT[axis] });
  const missing = (['top', 'bottom', 'footwear'] as Slot[]).filter(s => p.slotCounts && !p.slotCounts[s]);
  if (p.slotCounts && missing.length)
    rows.push({ icon: '➕', title: 'À compléter', value: missing.map(s => STYLE_WORDS[s]).join(', '), warn: true });
  return rows;
}
// libellé d'une suggestion : une « pièce unique » traditionnelle (jebba, kaftan…) n'est pas une robe
const SLOT_ICON: Record<string, string> = { top: '👚', bottom: '👖', onepiece: '👗', outer: '🧥', footwear: '👞', bag: '👜', accessory: '🧣' };
const suggSlot = (slot: string, traditional?: boolean) => (slot === 'onepiece' && traditional ? 'Tenue traditionnelle' : slotLabel(slot));
const chipSlot = (slot: Slot, gender?: string | null) =>
  slot === 'onepiece' ? (gender === 'Men' ? 'Tenue traditionnelle' : 'Robe / tenue traditionnelle') : slotLabel(slot);

const bar = (value: number, color: string) => (
  <div style={{ width: '100%', height: '8px', background: '#FFFFFF', borderRadius: '999px', margin: '10px 0 8px', overflow: 'hidden' }}>
    <div style={{ width: `${Math.max(0, Math.min(100, value))}%`, height: '100%', background: color, borderRadius: '999px' }} />
  </div>
);
const h3 = { fontSize: '1.2rem', marginBottom: '8px' } as const;
const sub = { color: 'var(--muted)', fontSize: '0.88rem', margin: '0 0 14px' } as const;

export default function Profile() {
  const { profile: contextProfile, setProfile: setContextProfile } = useApp();
  const [reload, setReload] = useState(0);
  const state = useAsync(getProfile, [reload]);
  const [profile, setProfile] = useState<StyleProfile>(contextProfile);
  const [slot, setSlot] = useState<Slot | ''>('');
  const [gender, setGender] = useState<Gender | ''>('');

  // uniquement quand un nouveau profil arrive (setContextProfile change à chaque rendu du contexte)
  useEffect(() => {
    if (state.data) { setProfile(state.data); setContextProfile(state.data); }
  }, [state.data]);   // eslint-disable-line react-hooks/exhaustive-deps

  const sugg = useAsync(
    () => getStyleSuggestions(slot || undefined, gender || undefined),
    [slot, gender],
  );

  const pct = (v?: number | null) => (v == null ? '—' : `${v} %`);
  const formality = profile.formalityPref;
  const slots = Object.entries(profile.slotCounts ?? {}).sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0));
  const maxSlot = Math.max(1, ...slots.map(([, n]) => n ?? 0));
  const live = true;

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
          {/* Bilan */}
          {live && (
            <section className="card card-lavender" aria-label="Bilan de votre garde-robe" style={{ marginBottom: '20px', padding: '18px 22px' }}>
              <h3 style={{ fontSize: '1.1rem', marginBottom: '12px' }}>🧾 Bilan de votre garde-robe</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '10px' }}>
                {bilan(profile).map(r => (
                  <div key={r.title} style={{ display: 'flex', gap: '12px', alignItems: 'flex-start', background: '#FFFFFF', borderRadius: '16px',
                                              padding: '12px 14px', border: r.warn ? '1px solid var(--pastel-butter-deep)' : '1px solid var(--line)' }}>
                    <span aria-hidden style={{ fontSize: '1.5rem', lineHeight: 1 }}>{r.icon}</span>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--muted)' }}>{r.title}</div>
                      <div style={{ fontSize: '1.05rem', fontWeight: 800, color: 'var(--ink)', display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                        {r.swatches?.map(c => <span key={c} aria-hidden style={{ width: '14px', height: '14px', borderRadius: '50%', background: swatch(c), border: '1px solid var(--line)' }} />)}
                        <span style={{ textTransform: 'none' }}>{r.value.charAt(0).toUpperCase() + r.value.slice(1)}</span>
                      </div>
                      {r.detail && <div style={{ fontSize: '0.8rem', color: 'var(--muted)', lineHeight: 1.4 }}>{r.detail}</div>}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Notes de l'analyse */}
          {live && !!profile.notes?.length && (
            <div role="status" className="card card-butter" style={{ marginBottom: '20px', padding: '12px 18px' }}>
              <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '0.88rem', lineHeight: 1.6 }}>
                {profile.notes?.map(n => <li key={n}>{n}</li>)}
              </ul>
            </div>
          )}

          {/* Résumé */}
          <section className="card" style={{ marginBottom: '28px', background: 'linear-gradient(135deg, #FFFFFF 0%, var(--pastel-pink-subtle) 100%)', padding: '22px' }}>
            <p style={{ color: 'var(--muted)', fontSize: '0.9rem', margin: 0 }}>Votre style le plus représenté</p>
            <h2 style={{ fontSize: '1.4rem', margin: '4px 0 2px' }}>{styleLabel(profile.dominantCluster) || 'à découvrir'}</h2>
            {profile.dominantShare != null && (
              <p style={{ color: 'var(--muted)', fontSize: '0.85rem', margin: 0 }}>{profile.dominantShare} % de vos pièces sont dans ce style</p>
            )}
            {!!profile.dominantPieces?.length && (
              <div className="chips" aria-label="Pièces de ce style" style={{ marginTop: '8px', marginBottom: 0 }}>
                {profile.dominantPieces.map(d => <span key={d.id} className="chip-tag chip-tag-lavender">{d.name || d.id}</span>)}
              </div>
            )}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px', marginTop: '16px' }}>
              {[
                { v: pct(profile.diversityScore), l: 'Variété de la garde-robe' },
                { v: formality == null ? '—' : `${formality.toFixed(1)} / 3`, l: `Formalité : ${formality == null ? '—' : FORMALITY[Math.round(formality)]}` },
                { v: AXIS_TITLE[axisOf(profile)], l: 'Orientation calculée' },
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
                Vos pièces sont comparées {profile.nStyles ? `aux ${profile.nStyles} styles` : 'aux styles'} d'un catalogue de référence
                d'après leurs caractéristiques (catégorie, couleur, usage, formalité, chaleur, saison){profile.space === 'photos' ? ' et leurs photos' : ''}.
              </p>
            )}
          </section>

          {/* Palette et répartition */}
          <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginBottom: '28px' }}>
            <div className="card" style={{ background: '#FFFFFF' }}>
              <h3 style={h3}>🎨 Votre palette</h3>
              <p style={sub}>Couleurs les plus présentes sur l'ensemble de vos pièces (tous styles confondus).</p>
              {profile.palette?.length ? (
                <div style={{ display: 'grid', gap: '8px' }}>
                  {profile.palette.map(p => (
                    <div key={p.color} style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.88rem' }}>
                      <span aria-hidden style={{ width: '22px', height: '22px', borderRadius: '50%', background: swatch(p.color), border: '1px solid var(--line)', flex: 'none' }} />
                      <span style={{ width: '110px' }}>{p.color.startsWith('#') ? p.color : colourLabel(p.color)}</span>
                      <div style={{ flex: 1 }}>{bar(p.weight * 100, 'var(--pastel-pink-deep)')}</div>
                      <strong style={{ width: '42px', textAlign: 'right' }}>{Math.round(p.weight * 100)} %</strong>
                      {p.pieces != null && <span style={{ width: '64px', color: 'var(--muted)', fontSize: '0.8rem' }}>{p.pieces} pièce{p.pieces > 1 ? 's' : ''}</span>}
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

          {/* Suggestions de l'Obj5 */}
          {live && (
            <section style={{ marginBottom: '28px' }}>
              <h3 style={h3}>🛍️ Pièces qui prolongent votre style</h3>
              <p style={sub}>
                Choisies dans un catalogue de référence, proches de votre garde-robe et classées selon votre orientation
                ({AXIS_TITLE[axisOf(profile)]}){sugg.data?.gender && <> · pour <strong>{sugg.data.gender === 'Men' ? 'homme' : 'femme'}</strong>
                {sugg.data.genderAuto ? ' (déduit de votre garde-robe)' : ''}</>}.
              </p>
              <div className="chips" role="group" aria-label="Pour">
                {([['', 'Automatique'], ['Women', '👩 Femme'], ['Men', '👨 Homme']] as const).map(([g, l]) => (
                  <button key={g} className="chip" style={{ fontSize: '0.8rem' }} aria-pressed={gender === g} onClick={() => setGender(g)}>{l}</button>
                ))}
              </div>
              <div className="chips" role="group" aria-label="Catégorie">
                <button className="chip" aria-pressed={slot === ''} onClick={() => setSlot('')}>Toutes</button>
                {SLOTS.filter(s => !sugg.data?.available || (sugg.data.available[s] ?? 0) > 0 || slot === s).map(s => (
                  <button key={s} className="chip" aria-pressed={slot === s} onClick={() => setSlot(s)}>
                    {s === 'onepiece' && sugg.data?.gender === 'Men' ? '👘' : SLOT_ICON[s]} {chipSlot(s, sugg.data?.gender)}
                  </button>
                ))}
              </div>
              {sugg.loading && <p role="status" style={sub}>Recherche de pièces…</p>}
              {sugg.error && <p role="alert" style={{ ...sub, color: 'var(--danger)' }}>Suggestions indisponibles : {sugg.error.message}</p>}
              {sugg.data && (sugg.data.items.length ? (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '12px' }}>
                  {sugg.data.items.map(it => (
                    <article key={it.id} className="card" style={{ background: '#FFFFFF', padding: '14px 16px', display: 'grid', gap: '8px', alignContent: 'start' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <div aria-hidden style={{ width: '52px', height: '52px', flex: 'none', borderRadius: '14px', display: 'grid', placeItems: 'center', fontSize: '26px',
                                                   background: `linear-gradient(135deg, ${swatch(it.colour[0] ?? 'grey')} 0%, ${swatch(it.colour[1] ?? it.colour[0] ?? 'grey')} 100%)`,
                                                   border: '1px solid var(--line)' }}>
                          <span style={{ filter: 'drop-shadow(0 1px 2px rgba(255,255,255,.9))' }}>{it.slot === 'onepiece' && it.traditional ? '👘' : SLOT_ICON[it.slot] ?? '🛍️'}</span>
                        </div>
                        <div style={{ minWidth: 0 }}>
                          <div style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--ink)' }}>{it.name || typeLabel(it.type)}</div>
                          <div style={{ fontSize: '0.78rem', color: 'var(--muted)' }}>
                            {[suggSlot(it.slot, it.traditional), typeLabel(it.type)].filter((x, i, a) => x && x !== 'Autre' && a.indexOf(x) === i).join(' · ')}
                            {it.usage ? ` · ${usageLabel(it.usage)}` : ''}
                          </div>
                        </div>
                      </div>
                      <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', color: 'var(--muted)' }}>
                          <span>Correspondance avec votre style</span><strong style={{ color: 'var(--ink)' }}>{it.match} %</strong>
                        </div>
                        {bar(it.match, 'var(--pastel-mint-deep)')}
                      </div>
                      {it.reasons.length > 0 && (
                        <div className="chips" style={{ marginBottom: 0, gap: '6px' }}>
                          {it.reasons.map(r => <span key={r} className="chip-tag chip-tag-mint" style={{ fontSize: '0.72rem' }}>✓ {r}</span>)}
                        </div>
                      )}
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
