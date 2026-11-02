import { useState } from 'react';
import { useAsync } from '../hooks/useAsync';
import { getGapAnalysis, searchShops } from '../services/gaps';
import type { ClothingItem, GapSuggestion, ShopOption } from '../types';
import { slotLabel } from '../components/ui/ItemFields';
import { ItemDetailModal } from '../components/ui/ItemDetailModal';

// Rapport statique de l'Obj4 en anglais (« black dress ») -> français ; un mot inconnu est gardé tel quel
const GAP_WORDS: Record<string, string> = {
  dress: 'robe', blouse: 'chemisier', skirt: 'jupe', flats: 'ballerines', coat: 'manteau', jacket: 'veste', shirt: 'chemise',
  't-shirt': 't-shirt', tshirt: 't-shirt', jeans: 'jean', trousers: 'pantalon', pants: 'pantalon', sneakers: 'baskets',
  shoes: 'chaussures', heels: 'escarpins', boots: 'bottes', bag: 'sac', handbag: 'sac à main', sweater: 'pull', top: 'haut',
  black: 'noir', white: 'blanc', grey: 'gris', gray: 'gris', beige: 'beige', brown: 'marron', blue: 'bleu', navy: 'bleu marine',
  red: 'rouge', pink: 'rose', green: 'vert', yellow: 'jaune', purple: 'violet', orange: 'orange',
};
const FEMININE = new Set(['robe', 'jupe', 'veste', 'chemise']);
const FEM_ADJ: Record<string, string> = { noir: 'noire', blanc: 'blanche', gris: 'grise', vert: 'verte', violet: 'violette', marron: 'marron' };
const describeGap = (d: string) => {
  const words = d.toLowerCase().split(/\s+/).filter(Boolean);
  if (words.length === 2 && GAP_WORDS[words[0]] && GAP_WORDS[words[1]]) {   // « couleur nom » -> « nom couleur »
    const noun = GAP_WORDS[words[1]];
    const adj = GAP_WORDS[words[0]];
    return `${noun} ${FEMININE.has(noun) ? FEM_ADJ[adj] || adj : adj}`;
  }
  return words.map(w => GAP_WORDS[w] || w).join(' ');
};
const SLOT_ICON: Record<string, string> = { top: '👚', bottom: '👖', onepiece: '👗', outer: '🧥', footwear: '👠', bag: '👜', accessory: '🧣' };
const cap = (t: string) => t.charAt(0).toUpperCase() + t.slice(1);
const sub = { color: 'var(--muted)', fontSize: '0.86rem', margin: '4px 0 0', lineHeight: 1.5 } as const;

type Shop = { loading?: boolean; error?: string; options?: ShopOption[]; order?: 'asc' | 'desc' };
const SHOW = 3;   // résultats affichés par recherche
const fmt = (v: number) => v.toLocaleString('fr-FR', { minimumFractionDigits: v % 1 ? 2 : 0, maximumFractionDigits: 3 });
const money = (o: ShopOption) => (o.price == null ? 'Prix sur le site'
  : `${fmt(o.price)} ${o.currency ?? ''}`.trim() + (o.currency && o.currency !== 'TND' && o.priceTnd != null ? ` (≈ ${fmt(Math.round(o.priceTnd))} TND)` : ''));
/** 3 résultats : fiches produit d'abord, puis prix connus triés (croissant ou décroissant), puis prix inconnus. */
const pickShops = (opts: ShopOption[], order: 'asc' | 'desc') => {
  const val = (o: ShopOption) => o.priceTnd ?? null;   // devises différentes : comparées en dinars
  const rank = (o: ShopOption) => (o.product ? 0 : 2) + (val(o) == null ? 1 : 0);
  return [...opts].sort((x, y) => rank(x) - rank(y)
    || (val(x) != null && val(y) != null ? (order === 'asc' ? val(x)! - val(y)! : val(y)! - val(x)!) : 0)).slice(0, SHOW);
};

const likelyOf = (g: GapSuggestion) => g.gain_likely ?? g.unlockedOutfits;
const gainText = (g: GapSuggestion) => {
  const lo = g.gain_lower ?? g.unlockedOutfits, hi = g.gain_upper ?? g.unlockedOutfits;
  return lo === hi ? `+${hi} tenue${hi > 1 ? 's' : ''}` : `de +${lo} à +${hi} tenues`;
};

export default function Gaps() {
  const [refresh, setRefresh] = useState(0);
  const state = useAsync(() => getGapAnalysis(refresh > 0), [refresh]);
  const [shops, setShops] = useState<Record<string, Shop>>({});
  const [maxPrice, setMaxPrice] = useState('');
  const [selected, setSelected] = useState<ClothingItem | null>(null);

  async function findShops(g: GapSuggestion) {
    setShops(s => ({ ...s, [g.id]: { loading: true } }));
    try {
      const price = maxPrice.trim() ? Number(maxPrice) : undefined;
      const r = await searchShops(g.description, g.slot, price != null && !Number.isNaN(price) ? price : undefined);
      setShops(s => ({ ...s, [g.id]: { options: r.options } }));
    } catch (e) {
      setShops(s => ({ ...s, [g.id]: { error: e instanceof Error ? e.message : String(e) } }));
    }
  }

  const a = state.data;
  return (
    <>
      <header className="page-head">
        <div>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            Pièces à ajouter <span style={{ fontSize: '1.6rem' }}>🎯</span>
          </h1>
          <p className="page-subtitle">
            Les pièces qui, ajoutées à votre garde-robe, vous permettraient de créer le plus de nouvelles tenues.
          </p>
        </div>
        {(
          <button className="btn-sm btn-secondary" style={{ borderRadius: '999px' }} disabled={state.loading} onClick={() => setRefresh(r => r + 1)}>
            {state.loading ? 'Analyse…' : '↻ Nouvelle analyse'}
          </button>
        )}
      </header>

      {/* ---------- Analyse réelle (objectif 4) ---------- */}
      {state.loading && <p role="status" style={sub}>Analyse de votre garde-robe : propositions de pièces, accords entre pièces, comptage des tenues…</p>}
      {state.error && (
        <div role="alert" style={{ background: 'var(--danger-bg)', color: 'var(--danger)', padding: '12px 18px', borderRadius: '16px', marginBottom: '20px' }}>
          Analyse indisponible : {state.error.message}
        </div>
      )}

      {a && !state.loading && (
        <>
          {a.mode === 'exemple' ? (
            <div role="status" className="card card-butter" style={{ marginBottom: '20px', padding: '12px 18px', fontSize: '0.9rem' }}>
              Exemple de résultat : {a.notice}
            </div>
          ) : (
            <section className="card card-mint" style={{ marginBottom: '24px', padding: '22px' }}>
              <h2 style={{ fontSize: '1.3rem', marginBottom: '6px' }}>
                Aujourd'hui : environ {a.outfitsNow?.likely ?? a.outfitsNow?.lower ?? '—'} tenues possibles
              </h2>
              <p style={{ ...sub, color: 'var(--ink)' }}>
                Avec vos {a.pieces} pièces (hors accessoires, doublons comptés une fois)
                {a.outfitsNow && <> · fourchette : de {a.outfitsNow.lower} (associations sûres) à {a.outfitsNow.upper} (avec les incertaines)</>}.
              </p>
              <p style={sub}>
                Pièces proposées par {a.source === 'ia' ? "l'IA d'après votre garde-robe" : 'une liste de pièces de base (IA indisponible)'} ·
                {' '}{a.pairsScored} associations vérifiées.
              </p>
            </section>
          )}

          {a.mode === 'analyse' && a.shoppingEnabled && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px', flexWrap: 'wrap' }}>
              <label htmlFor="gap-price" style={{ fontSize: '0.86rem', fontWeight: 600 }}>Budget maximum (TND) pour la recherche en ligne</label>
              <input id="gap-price" className="form-input" type="number" min={0} placeholder="sans limite" value={maxPrice}
                     onChange={e => setMaxPrice(e.target.value)} style={{ width: '130px' }} />
            </div>
          )}

          {a.gaps.length === 0 && <p style={sub}>Aucune pièce manquante à proposer pour le moment.</p>}
          <ul className="rows">
            {a.gaps.map(g => {
              const sh = shops[g.id];
              const best = Math.max(1, ...a.gaps.map(likelyOf));
              const n = likelyOf(g);
              return (
                <li key={g.id} className="row" style={{ alignItems: 'flex-start', flexWrap: 'wrap' }}>
                  <div aria-hidden="true" style={{ width: '84px', height: '100px', borderRadius: '16px', background: 'var(--pastel-lavender-soft)', display: 'grid', placeItems: 'center', fontSize: '34px', flex: 'none' }}>
                    {SLOT_ICON[g.slot] || '🛍️'}
                  </div>
                  <div style={{ flex: 1, minWidth: '220px' }}>
                    <span className="chip-tag chip-tag-lavender">Priorité {g.rank} · {slotLabel(g.slot)}</span>
                    <h3 style={{ marginTop: '6px' }}>{cap(a.mode === 'exemple' ? describeGap(g.description) : g.description)}</h3>
                    {g.rationale && <p style={sub}>{g.rationale}</p>}
                    {a.mode === 'analyse' ? (
                      <div style={{ marginTop: '8px', maxWidth: '420px' }}>
                        <span style={{ fontWeight: 700, fontSize: '1rem', color: n ? 'var(--pastel-mint-deep)' : 'var(--muted)' }}>
                          {n ? `≈ +${n} nouvelle${n > 1 ? 's' : ''} tenue${n > 1 ? 's' : ''}` : 'Aucune nouvelle tenue estimée'}
                        </span>
                        <div style={{ height: '6px', background: 'var(--paper)', borderRadius: '999px', margin: '6px 0 4px', overflow: 'hidden' }}>
                          <div style={{ width: `${(100 * n) / best}%`, height: '100%', background: 'var(--pastel-mint-deep)', borderRadius: '999px' }} />
                        </div>
                        <span style={{ fontSize: '0.76rem', color: 'var(--muted)' }}>
                          Fourchette : {gainText(g)}
                          {!n && g.proxy && ` · « ${g.proxy.name || slotLabel(g.proxy.slot)} », qui sert à la simuler, ne s'accorde avec aucune de vos tenues selon le modèle : estimation peu fiable`}
                        </span>
                      </div>
                    ) : (
                      <p style={{ ...sub, color: 'var(--ink)' }}>Nouvelles tenues possibles : <span style={{ fontWeight: 700 }}>{gainText(g)}</span></p>
                    )}
                    {g.proxy && (
                      <p style={sub}>
                        Estimée en la simulant avec votre pièce{' '}
                        <button className="btn-sm btn-secondary" style={{ borderRadius: '999px', fontSize: '0.78rem' }} onClick={() => setSelected(g.proxy!)}>
                          {g.proxy.name || slotLabel(g.proxy.slot)}
                        </button>
                        {g.proxyColourDiffers && ' (couleur différente : estimation moins précise)'}
                      </p>
                    )}
                    {a.mode === 'analyse' && (
                      <div style={{ marginTop: '8px' }}>
                        <button className="btn-sm btn-secondary" style={{ borderRadius: '999px' }} disabled={sh?.loading} onClick={() => findShops(g)}
                                title={`Recherche web : « ${g.description} buy online »`}>
                          {sh?.loading ? 'Recherche…' : '🔎 Recherche en ligne'}
                        </button>
                        {sh?.error && <p role="alert" style={{ ...sub, color: 'var(--danger)' }}>{sh.error}</p>}
                        {sh?.options && (sh.options.length ? (
                          <div style={{ marginTop: '10px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginBottom: '8px' }}>
                              <span style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>
                                {Math.min(SHOW, sh.options.length)} sur {sh.options.length} résultat{sh.options.length > 1 ? 's' : ''} · trier par
                              </span>
                              {(['asc', 'desc'] as const).map(ord => (
                                <button key={ord} className="chip" style={{ fontSize: '0.75rem', padding: '4px 10px' }}
                                        aria-pressed={(sh.order ?? 'asc') === ord}
                                        onClick={() => setShops(s => ({ ...s, [g.id]: { ...s[g.id], order: ord } }))}>
                                  {ord === 'asc' ? 'Prix croissant' : 'Prix décroissant'}
                                </button>
                              ))}
                            </div>
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(190px, 1fr))', gap: '10px' }}>
                              {pickShops(sh.options, sh.order ?? 'asc').map(o => (
                                <a key={o.url} href={o.url} target="_blank" rel="noreferrer noopener" className="card"
                                   style={{ display: 'grid', gap: '6px', alignContent: 'start', padding: '10px', background: '#FFFFFF', color: 'inherit', textDecoration: 'none' }}>
                                  <div style={{ height: '150px', borderRadius: '12px', background: 'var(--paper)', display: 'grid', placeItems: 'center', overflow: 'hidden' }}>
                                    {o.imageUrl
                                      ? <img src={o.imageUrl} alt={o.title} loading="lazy" referrerPolicy="no-referrer"
                                             onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
                                             style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }} />
                                      : <span style={{ fontSize: '0.78rem', color: 'var(--muted)' }}>Pas de photo</span>}
                                  </div>
                                  <span style={{ fontSize: '0.86rem', fontWeight: 700, lineHeight: 1.3, color: 'var(--ink)', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{o.title}</span>
                                  <span style={{ fontSize: '1rem', fontWeight: 800, color: o.price == null ? 'var(--muted)' : 'var(--pastel-mint-deep)' }}>{money(o)}</span>
                                  <span style={{ fontSize: '0.74rem', color: 'var(--muted)' }}>{o.site}</span>
                                  {o.description && (
                                    <span style={{ fontSize: '0.78rem', lineHeight: 1.4, display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{o.description}</span>
                                  )}
                                </a>
                              ))}
                            </div>
                            <p style={{ ...sub, fontSize: '0.74rem' }}>Prix et photos tels que trouvés en ligne : vérifiez sur le site du vendeur (taille, livraison, prix final).</p>
                          </div>
                        ) : <p style={sub}>Aucune boutique trouvée{maxPrice ? ' dans ce budget' : ''}.</p>)}
                      </div>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>

          {a.unscorable.length > 0 && (
            <section className="card" style={{ background: '#FFFFFF', marginTop: '20px' }}>
              <h3 style={{ fontSize: '1.05rem' }}>Autres idées, non chiffrées</h3>
              <p style={sub}>Accessoires (non comptés dans les tenues) ou catégories absentes de votre garde-robe : impossible d'estimer les tenues gagnées.</p>
              <ul style={{ margin: '8px 0 0', paddingLeft: '20px', fontSize: '0.88rem', lineHeight: 1.6 }}>
                {a.unscorable.map(u => <li key={u.description}><strong>{u.description}</strong> ({slotLabel(u.slot)}){u.rationale ? ` — ${u.rationale}` : ''}</li>)}
              </ul>
            </section>
          )}

          {a.mode === 'analyse' && (
            <p style={{ ...sub, fontSize: '0.78rem', marginTop: '18px' }}>
              Estimation indicative : chaque pièce proposée est simulée par une de vos pièces de même catégorie ; une association
              compte quand le modèle d'accord entre pièces la juge plus probable qu'improbable (seuils pas encore calibrés).
            </p>
          )}
        </>
      )}

      <ItemDetailModal item={selected} onClose={() => setSelected(null)} />
    </>
  );
}
