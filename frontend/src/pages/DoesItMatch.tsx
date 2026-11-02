import { useState } from 'react';
import { adviseCandidate, scoreCandidate, type CompatAdvice } from '../services/compatibility';
import { listItems } from '../services/wardrobe';
import { useAsync } from '../hooks/useAsync';
import type { CompatibilityResult, ClothingItem, PairScore } from '../types';
import { PhotoPicker } from '../components/ui/PhotoPicker';
import { ItemTile } from '../components/ui/ItemTile';
import { ItemDetailModal } from '../components/ui/ItemDetailModal';

// catégories de l'Obj2 -> libellé
const CAT_FR: Record<string, string> = {
  tops: 'Haut', bottoms: 'Bas', 'all-body': 'Robe / combinaison', outerwear: 'Veste / manteau', shoes: 'Chaussures', bags: 'Sac',
  accessories: 'Accessoire', hats: 'Chapeau', jewellery: 'Bijou', scarves: 'Écharpe', sunglasses: 'Lunettes de soleil',
};
const VERDICT_STYLE: Record<string, { color: string; label: string }> = {
  'va bien': { color: 'var(--pastel-mint-deep)', label: 'Va bien' },
  moyen: { color: 'var(--pastel-butter-deep)', label: 'Moyen' },
  'à éviter': { color: 'var(--pastel-pink-deep)', label: 'À éviter' },
};

export default function DoesItMatch() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [preview, setPreview] = useState('');
  const [candidateName, setCandidateName] = useState('');
  const [result, setResult] = useState<CompatibilityResult | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [selectedItem, setSelectedItem] = useState<ClothingItem | null>(null);
  const [advice, setAdvice] = useState<CompatAdvice | null>(null);
  const [adviceBusy, setAdviceBusy] = useState(false);
  const [adviceNote, setAdviceNote] = useState('');
  const live = useAsync(listItems);   // garde-robe réelle (mode API) pour retrouver les partenaires renvoyés par /compat

  // Partenaires = ceux renvoyés par l'Objectif 2 (meilleurs scores de paire), retrouvés dans la garde-robe affichée
  const source = live.data || [];
  const withItems = (list: PairScore[] = []) => list
    .map(p => ({ item: source.find(i => i.id === p.id), score: p.pair_score01, verdict: p.verdict }))
    .filter((p): p is { item: ClothingItem; score: number; verdict: PairScore['verdict'] } => !!p.item);
  const partnerItems = withItems(result?.partners).sort((a, b) => b.score - a.score).slice(0, 4);
  const clashItems = withItems(result?.clashing);
  const duplicateItem = result?.duplicate?.is_duplicate ? source.find(i => i.id === result.duplicate!.id) : undefined;

  async function score(f: File, category?: string) {
    setBusy(true);
    setError('');
    setResult(null);
    setAdvice(null); setAdviceNote('');
    try {
      setResult(await scoreCandidate(f, category));
    } catch (e) {
      setError(`Impossible d'analyser cette photo : ${e instanceof Error ? e.message : e}`);
    } finally {
      setBusy(false);
    }
  }

  async function askAdvice() {
    if (!file || !result) return;
    setAdviceBusy(true); setAdviceNote('');
    try {
      const r = await adviseCandidate(file, result.category);
      setAdvice(r.advice); setAdviceNote(r.adviceNote || '');
    } catch (e) {
      setAdviceNote(`Conseil indisponible : ${e instanceof Error ? e.message : e}`);
    } finally {
      setAdviceBusy(false);
    }
  }
  const nameOf = (id: string) => source.find(i => i.id === id)?.name || id;

  function onPick(f: File) {
    setFile(f);
    setCandidateName('');
    setPreview(URL.createObjectURL(f));
    score(f);
  }

  const getScoreTheme = (score: number) => {
    if (score >= 70) return { bg: 'var(--pastel-mint-soft)', color: 'var(--pastel-mint-deep)', label: 'Bon choix',
                              headline: 'Elle ira bien avec votre garde-robe.' };
    if (score >= 40) return { bg: 'var(--pastel-butter-soft)', color: 'var(--pastel-butter-deep)', label: 'À réfléchir',
                              headline: 'Elle s\'associe avec une partie de votre garde-robe.' };
    return { bg: 'var(--pastel-pink-soft)', color: 'var(--pastel-pink-deep)', label: 'Peu assortie',
             headline: 'Elle s\'accorde peu avec votre garde-robe actuelle.' };
  };

  return (
    <>
      <header className="page-head">
        <div>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            Ça va avec ma garde-robe ? <span style={{ fontSize: '1.6rem' }}>🛍️</span>
          </h1>
          <p className="page-subtitle">
            Avant d'acheter, prenez la pièce en photo : nous vérifions si elle s'accorde avec votre garde-robe et si vous possédez déjà la même.
          </p>
        </div>
      </header>

      {error && (
        <div
          role="alert"
          style={{
            background: 'var(--danger-bg)',
            color: 'var(--danger)',
            padding: '12px 18px',
            borderRadius: '16px',
            marginBottom: '20px',
            fontSize: '0.9rem',
          }}
        >
          {error}
        </div>
      )}

      {!preview && (
        <div
          className="card"
          style={{
            maxWidth: '640px',
            margin: '20px auto',
            textAlign: 'center',
            padding: '48px 32px',
            border: '2px dashed var(--pastel-pink)',
            background: 'linear-gradient(145deg, #FFFFFF 0%, var(--pastel-pink-subtle) 100%)',
          }}
        >
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>🛍️</div>
          <h2>Testez une pièce avant de l'acheter</h2>
          <p style={{ color: 'var(--muted)', maxWidth: '440px', margin: '8px auto 24px', fontSize: '0.95rem' }}>
            Prenez en photo un article, en magasin ou en ligne : nous le comparons à toute votre garde-robe et vous montrons avec quelles pièces il ira le mieux.
          </p>
          <PhotoPicker label="Choisir une photo à tester" onPick={onPick} busy={busy} />
        </div>
      )}

      {preview && (
        <section className="split">
          {/* Candidate Card */}
          <div className="card" style={{ padding: '20px' }}>
            <span
              style={{
                display: 'inline-block',
                fontSize: '0.75rem',
                fontWeight: 700,
                textTransform: 'uppercase',
                color: 'var(--pastel-pink-deep)',
                background: 'var(--pastel-pink-soft)',
                padding: '4px 10px',
                borderRadius: '999px',
                marginBottom: '12px',
              }}
            >
              Pièce testée
            </span>

            <div style={{ width: '100%', aspectRatio: '3/4', borderRadius: '18px', overflow: 'hidden', background: 'var(--paper)' }}>
              <img
                src={preview}
                alt="Article scanné"
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
            </div>

            <div style={{ marginTop: '14px' }}>
              <h3 style={{ fontSize: '1.2rem' }}>
                {candidateName || (result?.category ? CAT_FR[result.category] || result.category : 'Pièce à tester')}
              </h3>
              <p style={{ color: 'var(--muted)', fontSize: '0.85rem', margin: '4px 0 0' }}>
                {busy ? 'Analyse en cours…' : result?.compared ? `Comparée à ${result.compared} pièces de votre garde-robe` : 'Comparée à votre garde-robe'}
              </p>
              {file && result?.categories && (
                <div style={{ marginTop: '12px' }}>
                  <label htmlFor="dim-cat" style={{ fontSize: '0.82rem', fontWeight: 600, display: 'block', marginBottom: '4px' }}>
                    Type de pièce {result.category === result.guessedCategory ? '(reconnu sur la photo)' : '(corrigé)'}
                  </label>
                  <select id="dim-cat" className="form-input" value={result.category} disabled={busy}
                          onChange={e => score(file, e.target.value)} style={{ width: '100%' }}>
                    {result.categories.map(c => <option key={c} value={c}>{CAT_FR[c] || c}</option>)}
                  </select>
                </div>
              )}
              <div style={{ marginTop: '12px' }}>
                <PhotoPicker label="Tester une autre photo" onPick={onPick} busy={busy} className="btn btn-secondary" />
              </div>
            </div>
          </div>

          {/* Results Column */}
          {busy && (
            <div className="skeleton" style={{ height: '360px' }}>
              <div style={{ padding: '32px', textAlign: 'center' }}>
                <div style={{ fontSize: '32px', marginBottom: '12px' }}>🪄</div>
                <h3>Analyse de la pièce…</h3>
              </div>
            </div>
          )}

          {result && !busy && (
            <div>
              {/* Duplicate Detection Alert (Objectif 2 contract feature) */}
              {result.duplicate && result.duplicate.is_duplicate && (
                <div
                  className="card card-butter"
                  style={{
                    marginBottom: '18px',
                    padding: '16px 20px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '14px',
                  }}
                >
                  <span style={{ fontSize: '28px' }}>⚠️</span>
                  <div>
                    <h4 style={{ margin: 0, fontSize: '0.95rem', color: 'var(--pastel-butter-deep)' }}>
                      Vous avez peut-être déjà cette pièce
                    </h4>
                    <p style={{ margin: '4px 0 0', fontSize: '0.82rem', color: 'var(--ink)' }}>
                      Elle ressemble beaucoup à « {duplicateItem?.name || 'une pièce de votre garde-robe'} ». Réfléchissez avant de l'acheter.
                    </p>
                  </div>
                  {duplicateItem && (
                    <img src={duplicateItem.imageCrop || duplicateItem.imageUrl} alt={duplicateItem.name || 'Pièce ressemblante'}
                         onClick={() => setSelectedItem(duplicateItem)}
                         style={{ width: '64px', height: '80px', objectFit: 'contain', borderRadius: '10px', background: '#fff', cursor: 'pointer', marginLeft: 'auto' }} />
                  )}
                </div>
              )}

              {/* Score Header Card */}
              <div
                className="card"
                style={{
                  background: 'linear-gradient(145deg, #FFFFFF 0%, #FAFAFC 100%)',
                  marginBottom: '20px',
                }}
              >
                <div className="score-badge-container">
                  <div
                    className="score-dial"
                    style={{
                      background: `linear-gradient(135deg, ${getScoreTheme(result.score).bg} 0%, #FFFFFF 100%)`,
                    }}
                  >
                    <span className="score-value" style={{ color: getScoreTheme(result.score).color }}>
                      {result.score}
                    </span>
                    <span className="score-max">/100</span>
                  </div>

                  <div className="score-info">
                    <span
                      style={{
                        fontSize: '0.78rem',
                        fontWeight: 700,
                        padding: '4px 10px',
                        borderRadius: '999px',
                        background: getScoreTheme(result.score).bg,
                        color: getScoreTheme(result.score).color,
                        display: 'inline-block',
                        marginBottom: '6px',
                      }}
                    >
                      {getScoreTheme(result.score).label}
                    </span>
                    <h3>{getScoreTheme(result.score).headline}</h3>
                  </div>
                </div>
              </div>

              {/* Insights Card */}
              <div className="card card-mint" style={{ marginBottom: '20px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                  <span style={{ fontSize: '18px' }}>💡</span>
                  <h4 style={{ fontSize: '1.05rem', color: 'var(--pastel-mint-deep)' }}>Notre analyse</h4>
                </div>
                <div style={{ display: 'grid', gap: '10px' }}>
                  {result.notes.map((n, i) => (
                    <div
                      key={i}
                      style={{
                        fontSize: '0.9rem',
                        color: 'var(--ink)',
                        display: 'flex',
                        alignItems: 'baseline',
                        gap: '8px',
                      }}
                    >
                      <span style={{ color: 'var(--pastel-mint-deep)', fontWeight: 700 }}>•</span>
                      <span>{n}</span>
                    </div>
                  ))}
                </div>
                <div style={{ marginTop: '14px', paddingTop: '12px', borderTop: '1px solid var(--line)' }}>
                  {!advice && (
                    <button className="btn-sm btn-secondary" style={{ borderRadius: '999px' }} disabled={adviceBusy || !file} onClick={askAdvice}
                            title="La photo est envoyée à l’IA (Gemini) pour un conseil ; le score ne change pas">
                      {adviceBusy ? 'La styliste regarde votre pièce…' : '💬 Conseil de la styliste IA'}
                    </button>
                  )}
                  {advice && (
                    <div style={{ display: 'grid', gap: '6px', fontSize: '0.9rem' }}>
                      <strong>💬 Conseil de la styliste IA</strong>
                      {advice.observation && <span style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>Vu sur la photo : {advice.observation}</span>}
                      <span>{advice.conseil}</span>
                      {advice.tenue.length > 0 && <span style={{ fontSize: '0.85rem' }}>À essayer avec : {advice.tenue.map(nameOf).join(', ')}</span>}
                      {advice.aEviter && <span style={{ fontSize: '0.85rem' }}>À éviter avec : {nameOf(advice.aEviter)}</span>}
                      <span style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>Rédigé par l’IA à partir du score du modèle, qui reste la référence.</span>
                    </div>
                  )}
                  {adviceNote && <p style={{ fontSize: '0.85rem', color: 'var(--muted)', marginTop: '6px' }}>{adviceNote}</p>}
                </div>
              </div>

              {/* Best Partners in Wardrobe */}
              <div className="card">
                <h4 style={{ fontSize: '1rem', marginBottom: '12px' }}>À porter avec</h4>
                <div className="grid small" style={{ marginTop: 0 }}>
                  {partnerItems.map(({ item, score, verdict }, idx) => (
                    <div key={item.id}>
                      <ItemTile item={item} index={idx} onClick={it => setSelectedItem(it)} />
                      <p style={{ fontSize: '0.8rem', color: 'var(--muted)', marginTop: '4px' }}>
                        {verdict && <span style={{ fontWeight: 700, color: VERDICT_STYLE[verdict]?.color }}>{VERDICT_STYLE[verdict]?.label} · </span>}
                        accord {Math.round(score * 100)} %
                      </p>
                    </div>
                  ))}
                </div>
                {partnerItems.length === 0 && (
                  <p style={{ fontSize: '0.88rem', color: 'var(--muted)' }}>Aucune pièce de votre garde-robe ne s'y associe vraiment.</p>
                )}
              </div>

              {clashItems.length > 0 && (
                <div className="card" style={{ marginTop: '20px' }}>
                  <h4 style={{ fontSize: '1rem', marginBottom: '12px' }}>À éviter avec</h4>
                  <div className="grid small" style={{ marginTop: 0 }}>
                    {clashItems.map(({ item, score }, idx) => (
                      <div key={item.id}>
                        <ItemTile item={item} index={idx} onClick={it => setSelectedItem(it)} />
                        <p style={{ fontSize: '0.8rem', color: 'var(--muted)', marginTop: '4px' }}>accord {Math.round(score * 100)} %</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </section>
      )}

      {/* Item Detail Modal */}
      <ItemDetailModal
        item={selectedItem}
        onClose={() => setSelectedItem(null)}
      />
    </>
  );
}
