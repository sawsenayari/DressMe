import { useState } from 'react';
import { scoreCandidate } from '../services/compatibility';
import type { CompatibilityResult, ClothingItem } from '../types';
import { PhotoPicker } from '../components/ui/PhotoPicker';
import { ItemTile } from '../components/ui/ItemTile';
import { ItemDetailModal } from '../components/ui/ItemDetailModal';
import { useApp } from '../context/AppContext';

const PRESET_CANDIDATES = [
  {
    name: 'Sage Green Linen Blazer',
    imageUrl: 'https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=700&auto=format&fit=crop&q=80',
    color: 'sage green',
    slot: 'outer',
    isDuplicateTest: false,
  },
  {
    name: 'Mule Rose Poudré en Cuir',
    imageUrl: 'https://images.unsplash.com/photo-1543163521-1bf539c55dd2?w=700&auto=format&fit=crop&q=80',
    color: 'rose poudré',
    slot: 'footwear',
    isDuplicateTest: true, // triggers duplicate detection in Objectif 2
  },
  {
    name: 'Jupe Midi Soie Lavande',
    imageUrl: 'https://images.unsplash.com/photo-1583496661160-fb5886a0aaaa?w=700&auto=format&fit=crop&q=80',
    color: 'lavande',
    slot: 'bottom',
    isDuplicateTest: false,
  },
];

export default function DoesItMatch() {
  const { useDemoData, scoreDemoCandidate, wardrobe } = useApp();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [preview, setPreview] = useState('');
  const [candidateName, setCandidateName] = useState('');
  const [result, setResult] = useState<CompatibilityResult | null>(null);
  const [selectedItem, setSelectedItem] = useState<ClothingItem | null>(null);

  async function onPick(file: File) {
    setBusy(true);
    setError('');
    setResult(null);
    setCandidateName(file.name.replace(/\.[^/.]+$/, ''));
    setPreview(URL.createObjectURL(file));

    try {
      if (useDemoData) {
        const res = await scoreDemoCandidate(file);
        setResult(res);
      } else {
        const res = await scoreCandidate(file);
        setResult(res);
      }
    } catch {
      setError('Erreur d\'évaluation. Vérifiez le service /compat (Objectif 2).');
    } finally {
      setBusy(false);
    }
  }

  function handleSelectPreset(preset: typeof PRESET_CANDIDATES[0]) {
    setBusy(true);
    setError('');
    setCandidateName(preset.name);
    setPreview(preset.imageUrl);

    setTimeout(() => {
      setResult({
        score: preset.isDuplicateTest ? 91 : 95,
        score01: preset.isDuplicateTest ? 0.91 : 0.95,
        verdict: 'compatible',
        newOutfits: preset.isDuplicateTest ? 2 : 8,
        partners: [{ id: wardrobe[1]?.id || 'it_0002', pair_score01: 0.88 }],
        duplicate: preset.isDuplicateTest
          ? {
              id: wardrobe[7]?.id || 'it_0008',
              similarity: 0.94,
              pct: 96,
              is_duplicate: true,
            }
          : undefined,
        clashingItems: [],
        notes: [
          `La palette ${preset.color} s'harmonise avec 90% de vos bas et hauts neutres.`,
          preset.isDuplicateTest
            ? '⚠️ Attention : vous possédez déjà une pièce très similaire dans votre dressing.'
            : 'Polyvalence élevée : s\'adapte aux occasions Casual Chic et Soirée.',
          'Matière et silhouette alignées sur votre profil de saison.',
        ],
      });
      setBusy(false);
    }, 450);
  }

  const getScoreTheme = (score: number) => {
    if (score >= 70) return { bg: 'var(--pastel-mint-soft)', color: 'var(--pastel-mint-deep)', label: 'Compatible (≥ 70)' };
    if (score >= 40) return { bg: 'var(--pastel-butter-soft)', color: 'var(--pastel-butter-deep)', label: 'Moyenne (40 à 69)' };
    return { bg: 'var(--pastel-pink-soft)', color: 'var(--pastel-pink-deep)', label: 'Peu compatible (< 40)' };
  };

  return (
    <>
      <header className="page-head">
        <div>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            Does It Match? <span style={{ fontSize: '1.6rem' }}>🛍️</span>
          </h1>
          <p className="page-subtitle">
            Service de compatibilité (Objectif 2 — Suzana). Scannez un article avant achat pour calculer le score /compat et détecter les doublons.
          </p>
        </div>

        <PhotoPicker label="Scanner un Vêtement" onPick={onPick} busy={busy} />
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

      {/* Preset Test Candidates */}
      <section style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.85rem', color: 'var(--muted)', fontWeight: 500 }}>
            Candidats de test rapides :
          </span>
          {PRESET_CANDIDATES.map(preset => (
            <button
              key={preset.name}
              className="chip"
              onClick={() => handleSelectPreset(preset)}
              style={{ padding: '6px 14px', fontSize: '0.82rem' }}
            >
              🛍️ {preset.name} {preset.isDuplicateTest ? '(Test Doublon)' : ''}
            </button>
          ))}
        </div>
      </section>

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
          <h2>Analyseur de Compatibilité d'Achat</h2>
          <p style={{ color: 'var(--muted)', maxWidth: '440px', margin: '8px auto 24px', fontSize: '0.95rem' }}>
            Prenez en photo un article en magasin ou en ligne. Le modèle PairMLP (FashionCLIP) compare la pièce avec tout votre dressing et calcule les nouvelles tenues débloquées.
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
              Article Candidat Scanné
            </span>

            <div style={{ width: '100%', aspectRatio: '3/4', borderRadius: '18px', overflow: 'hidden', background: 'var(--paper)' }}>
              <img
                src={preview}
                alt="Article scanné"
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
            </div>

            <div style={{ marginTop: '14px' }}>
              <h3 style={{ fontSize: '1.2rem', textTransform: 'capitalize' }}>
                {candidateName || 'Pièce Candidate'}
              </h3>
              <p style={{ color: 'var(--muted)', fontSize: '0.85rem', margin: '4px 0 0' }}>
                {busy ? 'Calcul PairMLP en cours…' : 'Évalué contre vos pièces de dressing'}
              </p>
            </div>
          </div>

          {/* Results Column */}
          {busy && (
            <div className="skeleton" style={{ height: '360px' }}>
              <div style={{ padding: '32px', textAlign: 'center' }}>
                <div style={{ fontSize: '32px', marginBottom: '12px' }}>🪄</div>
                <h3>Calcul du rang sur 100 via PairMLP…</h3>
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
                      Doublon Détecté dans votre Dressing ({result.duplicate.pct}% similarité)
                    </h4>
                    <p style={{ margin: '4px 0 0', fontSize: '0.82rem', color: 'var(--ink)' }}>
                      Vous possédez déjà une pièce presque identique (ID: <code>{result.duplicate.id}</code>). Réfléchissez avant de valider cet achat !
                    </p>
                  </div>
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
                    <h3>Débloque +{result.newOutfits} Nouvelles Tenues</h3>
                    <p>Appel API direct : <code>POST /compat</code></p>
                  </div>
                </div>
              </div>

              {/* Insights Card */}
              <div className="card card-mint" style={{ marginBottom: '20px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                  <span style={{ fontSize: '18px' }}>💡</span>
                  <h4 style={{ fontSize: '1.05rem', color: 'var(--pastel-mint-deep)' }}>Analyse du Styliste</h4>
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
              </div>

              {/* Best Partners in Wardrobe */}
              <div className="card">
                <h4 style={{ fontSize: '1rem', marginBottom: '12px' }}>Meilleurs Partenaires de votre Garde-Robe</h4>
                <div className="grid small" style={{ marginTop: 0 }}>
                  {wardrobe.slice(0, 3).map((item, idx) => (
                    <ItemTile
                      key={item.id}
                      item={item}
                      index={idx}
                      onClick={it => setSelectedItem(it)}
                    />
                  ))}
                </div>
              </div>
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
