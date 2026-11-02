import { useEffect, useRef, useState } from 'react';
import { useAsync } from '../hooks/useAsync';
import { getOutfitOptions, recommendOutfits, sendOutfitFeedback } from '../services/outfits';
import type { FeedbackReason } from '../services/outfits';
import type { ClothingItem, Gender, RecommendedOutfit, RecommendRequest, RecommendResponse } from '../types';
import { ItemTile } from '../components/ui/ItemTile';
import { ItemDetailModal } from '../components/ui/ItemDetailModal';
import { MannequinView } from '../components/ui/MannequinView';
import { colourLabel, typeLabel } from '../components/ui/ItemFields';
import { getWeather, loadCity, saveCity } from '../services/weather';
import { useApp } from '../context/AppContext';

const CITIES = ['Tunis', 'Sfax', 'Sousse', 'Bizerte', 'Nabeul', 'Djerba'];
// Exemples d'agenda (un clic remplit le texte, que l'on peut ensuite modifier) : le texte est le seul contexte
const AGENDA_EXAMPLES = [
  { label: '💼 Réunion client', text: 'réunion client à 10h puis présentation' },
  { label: '🌙 Dîner en ville', text: 'dîner au restaurant ce soir' },
  { label: '🏃 Sport', text: 'séance de sport à la salle' },
  { label: '💍 Mariage', text: 'mariage de ma cousine ce soir' },
  { label: '🕌 الجمعة', text: 'نمشي للجامع نهار الجمعة' },
  { label: '☕ Coffee with friends', text: 'coffee with friends then a walk' },
];
const REASONS: { id: FeedbackReason; label: string }[] = [
  { id: 'too_hot', label: 'Trop chaud' },
  { id: 'too_cold', label: 'Trop froid' },
  { id: 'too_formal', label: 'Trop habillé' },
  { id: 'too_casual', label: 'Pas assez habillé' },
  { id: 'style', label: 'Pas mon style' },
];

const pct = (x: number) => `${Math.round(x * 100)} %`;
const box = { background: 'var(--surface)', padding: '14px 18px', borderRadius: '18px', border: '1px solid var(--line)' };
const label = { fontSize: '0.85rem', fontWeight: 600, color: 'var(--ink)', display: 'block', marginBottom: '8px' } as const;

const loadGender = (): Gender => {
  try { return localStorage.getItem('dressme_gender') === 'Men' ? 'Men' : 'Women'; } catch { return 'Women'; }
};

type CardState = { status: 'idle' | 'busy' | 'worn' | 'asking'; msg?: string };

export default function Today() {
  const { useDemoData, getDemoOutfit } = useApp();
  const [gender, setGender] = useState<Gender>(loadGender);
  const [city, setCity] = useState(() => (CITIES.includes(loadCity()) ? loadCity() : 'Tunis'));
  const [agenda, setAgenda] = useState('');
  const [colours, setColours] = useState<string[]>([]);
  const [types, setTypes] = useState<string[]>([]);
  const [explain, setExplain] = useState(false);
  const [result, setResult] = useState<RecommendResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [cards, setCards] = useState<Record<number, CardState>>({});
  const seen = useRef<string[][]>([]);   // tenues déjà montrées : « Une autre » ne les repropose pas
  const queue = useRef<Promise<void>>(Promise.resolve());   // remplacements l'un après l'autre (jamais deux fois la même)
  const [selectedItem, setSelectedItem] = useState<ClothingItem | null>(null);
  const [displayMode, setDisplayMode] = useState<'grid' | 'mannequin'>('grid');

  const options = useAsync(() => getOutfitOptions(gender), [gender, useDemoData]);
  const wx = useAsync(() => getWeather(city), [city]);
  useEffect(() => saveCity(city), [city]);

  useEffect(() => { try { localStorage.setItem('dressme_gender', gender); } catch { /* stockage indisponible */ } }, [gender]);
  // envies qui n'existent plus pour ce genre : retirées
  useEffect(() => {
    if (!options.data) return;
    setColours(c => c.filter(x => options.data!.colours.includes(x)));
    setTypes(t => t.filter(x => options.data!.types.includes(x)));
  }, [options.data]);

  const request = (extra: Partial<RecommendRequest> = {}): RecommendRequest =>
    ({ gender, city, agenda: agenda.trim() || undefined, colours, types, explain, k: 3, ...extra });

  const propose = async (extra: Partial<RecommendRequest> = {}) => {
    setLoading(true); setError(''); setCards({});
    try {
      const r = await recommendOutfits(request(extra));
      setResult(r); seen.current = r.outfits.map(o => o.excludeKey);
    } catch (e) {
      setResult(null); setError(e instanceof Error ? e.message : String(e));
    } finally { setLoading(false); }
  };

  // premier affichage : une proposition avec les réglages par défaut
  useEffect(() => { if (!useDemoData) propose(); }, [useDemoData]);   // eslint-disable-line react-hooks/exhaustive-deps

  const setCard = (i: number, s: CardState) => setCards(c => ({ ...c, [i]: s }));

  // remplace la tenue i par une tenue jamais montrée (mêmes réglages que la proposition affichée)
  const replace = (i: number, note = '') => {
    if (!result) return Promise.resolve();
    setCard(i, { status: 'busy' });
    queue.current = queue.current.then(() => replaceNow(i, note));
    return queue.current;
  };
  const replaceNow = async (i: number, note: string) => {
    try {
      const r = await recommendOutfits(request({ k: 1, exclude_outfits: seen.current }));
      const o = r.outfits[0];
      if (!o) { setCard(i, { status: 'idle', msg: `${note}Plus d'autre tenue différente avec votre garde-robe.` }); return; }
      seen.current = [...seen.current, o.excludeKey];
      setResult(res => res && { ...res, outfits: res.outfits.map((x, j) => (j === i ? o : x)) });
      setCard(i, { status: 'idle', msg: note ? `${note}Voici une autre tenue.` : undefined });
    } catch (e) {
      setCard(i, { status: 'idle', msg: e instanceof Error ? e.message : String(e) });
    }
  };

  const wear = async (i: number, o: RecommendedOutfit) => {
    setCard(i, { status: 'busy' });
    try {
      await sendOutfitFeedback(o.excludeKey, true, o.features);
      setCard(i, { status: 'worn', msg: "C'est noté : vos prochaines suggestions en tiendront compte." });
    } catch (e) {
      setCard(i, { status: 'idle', msg: `Avis non enregistré : ${e instanceof Error ? e.message : e}` });
    }
  };

  const dislike = async (i: number, o: RecommendedOutfit, reason: FeedbackReason) => {
    setCard(i, { status: 'busy' });
    try { await sendOutfitFeedback(o.excludeKey, false, o.features, reason); } catch { /* l'autre tenue reste proposée */ }
    await replace(i, 'Avis noté. ');
  };

  const toggle = (list: string[], set: (v: string[]) => void, v: string) =>
    set(list.includes(v) ? list.filter(x => x !== v) : [...list, v]);

  const ctx = result?.context;
  const demo = useDemoData ? getDemoOutfit('casual', false) : null;

  return (
    <>
      <section style={{ marginBottom: '22px' }}>
        <h1 style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          Tenue du jour <span style={{ fontSize: '1.8rem' }}>✨</span>
        </h1>
        <p className="page-subtitle">
          Décrivez votre journée : la styliste choisit 3 tenues selon la météo de votre ville, votre agenda et vos envies.
        </p>
      </section>

      {/* Saisie */}
      <section className="card" style={{ marginBottom: '20px', display: 'grid', gap: '14px', background: '#FFFFFF' }}>
        <div style={{ display: 'flex', gap: '18px', flexWrap: 'wrap' }}>
          <div>
            <span style={label}>Pour</span>
            <div className="chips" role="group" aria-label="Genre" style={{ marginBottom: 0 }}>
              {([['Women', '👩 Femme'], ['Men', '👨 Homme']] as const).map(([g, l]) => (
                <button key={g} className="chip" aria-pressed={gender === g} onClick={() => setGender(g)}>{l}</button>
              ))}
            </div>
          </div>
          <div>
            <label style={label} htmlFor="today-city">Ville</label>
            <select id="today-city" className="form-input" value={city} onChange={e => setCity(e.target.value)} style={{ minWidth: '160px' }}>
              {(options.data?.cities ?? CITIES).map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div aria-label="Météo du jour" style={{ ...box, alignSelf: 'end', padding: '10px 16px', fontSize: '0.9rem' }}>
            {wx.loading ? 'Météo…'
              : wx.error ? <span style={{ color: 'var(--danger)' }}>Météo : {wx.error.message}</span>
              : !wx.data?.available ? 'Météo indisponible (température estimée)'
              : <>⛅ <strong>{wx.data.temperatureC}°C</strong> (ressenti {wx.data.feelsLikeC}°C) · 🌧️ pluie {wx.data.rainPct} % · 💨 {wx.data.windKmh} km/h</>}
          </div>
        </div>

        <div>
          <label style={label} htmlFor="today-agenda">📅 Votre agenda du jour (français, arabe ou anglais)</label>
          <input
            id="today-agenda" className="form-input" dir="auto" value={agenda} maxLength={300}
            placeholder="ex. réunion client à 10h · عرس في الليل · dinner with friends"
            onChange={e => setAgenda(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !loading && !useDemoData) propose(); }}
            style={{ width: '100%' }}
          />
          <div className="chips" role="group" aria-label="Exemples d'agenda" style={{ marginTop: '8px', marginBottom: 0 }}>
            {AGENDA_EXAMPLES.map(a => (
              <button key={a.label} className="chip" style={{ fontSize: '0.78rem' }} aria-pressed={agenda === a.text}
                      onClick={() => setAgenda(a.text)}>{a.label}</button>
            ))}
          </div>
        </div>

        <details>
          <summary style={{ cursor: 'pointer', fontWeight: 600, fontSize: '0.9rem' }}>
            🎨 Mes envies (facultatif){colours.length + types.length ? ` · ${colours.length + types.length} choisie(s)` : ''}
          </summary>
          <p style={{ fontSize: '0.8rem', color: 'var(--muted)', margin: '6px 0 10px' }}>Rien de coché = aucun filtre.</p>
          {options.error && <p style={{ fontSize: '0.8rem', color: 'var(--danger)' }}>Envies indisponibles : {options.error.message}</p>}
          {options.data && (
            <>
              <span style={label}>Couleurs</span>
              <div className="chips" role="group" aria-label="Couleurs souhaitées">
                {options.data.colours.map(c => (
                  <button key={c} className="chip" style={{ fontSize: '0.78rem' }} aria-pressed={colours.includes(c)}
                          onClick={() => toggle(colours, setColours, c)}>{colourLabel(c)}</button>
                ))}
              </div>
              <span style={label}>Types de vêtements</span>
              <div className="chips" role="group" aria-label="Types souhaités" style={{ marginBottom: 0 }}>
                {options.data.types.map(t => (
                  <button key={t} className="chip" style={{ fontSize: '0.78rem' }} aria-pressed={types.includes(t)}
                          onClick={() => toggle(types, setTypes, t)}>{typeLabel(t)}</button>
                ))}
              </div>
            </>
          )}
        </details>

        <div style={{ display: 'flex', alignItems: 'center', gap: '18px', flexWrap: 'wrap' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.9rem', cursor: 'pointer' }}>
            <input type="checkbox" checked={explain} disabled={loading}
                   onChange={e => {   // cocher / décocher relance la proposition, avec ou sans les explications
                     const v = e.target.checked;
                     setExplain(v);
                     if (result && !useDemoData) propose({ explain: v });
                   }} />
            Explications de la styliste IA
          </label>
          <button className="btn" onClick={() => propose()} disabled={loading || useDemoData}>
            {loading ? 'Recherche des tenues…' : '✨ Proposer des tenues'}
          </button>
          {useDemoData && <span style={{ fontSize: '0.82rem', color: 'var(--muted)' }}>Mode démonstration : connectez la garde-robe pour des propositions réelles.</span>}
        </div>
      </section>

      {error && <div className="card card-peach" role="alert" style={{ marginBottom: '16px' }}>Tenues indisponibles : {error}</div>}

      {/* Contexte, avertissements, orchestration */}
      {result && ctx && (
        <section style={{ display: 'grid', gap: '12px', marginBottom: '20px' }}>
          <div style={{ ...box, fontSize: '0.9rem' }} aria-label="Contexte">
            <strong>{ctx.city}</strong> · 🌡️ {ctx.temperatureC}°C · 🌧️ pluie {ctx.rainPct} % · occasion <strong>{ctx.occasion}</strong>
            {ctx.formality != null && <> (formalité {ctx.formality}/3)</>}
            {' '}· lu par : <strong>{ctx.agent ?? 'aucun agenda'}</strong>
            {' '}· fiches locales : {ctx.rag.length ? ctx.rag.join(', ') : 'aucune'}
            {ctx.ramadan && ' · 🌙 Ramadan'}{ctx.eid && ' · 🎉 Aïd'}
            {ctx.notes && <div style={{ color: 'var(--muted)', fontSize: '0.82rem', marginTop: '4px' }}>{ctx.notes}</div>}
          </div>

          {(result.warnings.length > 0 || result.message) && (
            <div className="card card-butter" role="status" style={{ padding: '12px 18px' }}>
              <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '0.88rem', lineHeight: 1.6 }}>
                {result.warnings.map(w => <li key={w}>⚠ {w}</li>)}
                {result.message && <li>{result.message}</li>}
              </ul>
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <div style={{ display: 'flex', background: 'var(--surface)', padding: '4px', borderRadius: '999px', border: '1px solid var(--line)' }}>
              {([['grid', 'Vue en grille'], ['mannequin', '🪞 Vue silhouette']] as const).map(([m, l]) => (
                <button key={m} className="chip" aria-pressed={displayMode === m} onClick={() => setDisplayMode(m)}
                        style={{ padding: '6px 14px', fontSize: '0.8rem', boxShadow: 'none', border: 'none' }}>{l}</button>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* 3 tenues */}
      {result && (
        <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '18px' }}>
          {result.outfits.map((o, i) => {
            const st = cards[i] ?? { status: 'idle' };
            return (
              <article key={`${i}-${o.id}`} className="card" style={{ background: '#FFFFFF', display: 'grid', gap: '10px', alignContent: 'start' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '8px', flexWrap: 'wrap' }}>
                  <h3 style={{ fontSize: '1.1rem' }}>Option {i + 1}</h3>
                  <span style={{ fontSize: '0.85rem' }}>
                    Score <strong>{pct(o.score)}</strong>{o.compat01 != null && <> · accord {pct(o.compat01)}</>}
                  </span>
                </div>
                <span className={`chip-tag ${o.alerts.length ? 'chip-tag-butter' : 'chip-tag-mint'}`} style={{ justifySelf: 'start' }}>{o.jury}</span>

                {displayMode === 'grid' ? (
                  <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(110px, 1fr))' }}>
                    {o.items.map((it, idx) => <ItemTile eager key={it.id} item={it} index={idx} onClick={setSelectedItem} />)}
                  </div>
                ) : (
                  <MannequinView items={[...o.items, ...o.accessories]} />
                )}

                <div style={{ fontSize: '0.85rem' }}>
                  <strong>Accessoires suggérés : </strong>
                  {o.accessories.length
                    ? o.accessories.map((a, j) => (
                        <button key={a.id} className="btn-sm btn-secondary" style={{ borderRadius: '999px', fontSize: '0.78rem', marginLeft: j ? 6 : 0 }}
                                onClick={() => setSelectedItem(a)}>{a.name || typeLabel(a.type)}</button>
                      ))
                    : <span style={{ color: 'var(--muted)' }}>aucun</span>}
                </div>

                <p style={{ fontSize: '0.9rem', lineHeight: 1.5, margin: 0 }}>
                  {o.explanation ? <>🪄 {o.explanation}</> : o.reasons.join(' · ')}
                </p>

                {o.alerts.length > 0 && (
                  <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '0.84rem', color: 'var(--danger)', lineHeight: 1.5 }}>
                    {o.alerts.map(a => <li key={a}>⚠ {a}</li>)}
                  </ul>
                )}

                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <button className={`btn-sm ${st.status === 'worn' ? 'btn-mint' : 'btn-secondary'}`} style={{ borderRadius: '999px' }}
                          disabled={st.status === 'busy' || st.status === 'worn'} onClick={() => wear(i, o)}>
                    {st.status === 'worn' ? '✓ Portée aujourd\'hui' : '👍 Je la porte'}
                  </button>
                  <button className="btn-sm btn-secondary" style={{ borderRadius: '999px' }} disabled={st.status === 'busy'} onClick={() => replace(i)}>
                    🔀 Une autre
                  </button>
                  <button className="btn-sm btn-secondary" style={{ borderRadius: '999px' }} disabled={st.status === 'busy'}
                          aria-expanded={st.status === 'asking'}
                          onClick={() => setCard(i, { status: st.status === 'asking' ? 'idle' : 'asking' })}>
                    👎 Pas pour moi
                  </button>
                </div>
                {st.status === 'asking' && (
                  <div className="chips" role="group" aria-label="Pourquoi ?" style={{ marginBottom: 0 }}>
                    {REASONS.map(r => (
                      <button key={r.id} className="chip" style={{ fontSize: '0.78rem' }} onClick={() => dislike(i, o, r.id)}>{r.label}</button>
                    ))}
                  </div>
                )}
                {st.status === 'busy' && <p role="status" style={{ fontSize: '0.82rem', color: 'var(--muted)', margin: 0 }}>Un instant…</p>}
                {st.msg && st.status !== 'busy' && <p role="status" style={{ fontSize: '0.82rem', color: 'var(--muted)', margin: 0 }}>{st.msg}</p>}
              </article>
            );
          })}
        </section>
      )}

      {/* Mode démonstration : tenue d'exemple, sans service */}
      {demo && (
        <section className="card" style={{ background: '#FFFFFF' }}>
          <h3 style={{ fontSize: '1.1rem', marginBottom: '10px' }}>Exemple de tenue</h3>
          <div className="grid">
            {demo.items.map((it, idx) => <ItemTile eager key={it.id} item={it} index={idx} onClick={setSelectedItem} />)}
          </div>
          {demo.reason && <p style={{ fontSize: '0.9rem', marginTop: '10px' }}>{demo.reason}</p>}
        </section>
      )}

      <ItemDetailModal item={selectedItem} onClose={() => setSelectedItem(null)} />
    </>
  );
}
