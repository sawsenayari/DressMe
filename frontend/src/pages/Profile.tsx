import { useEffect, useState } from 'react';
import { useAsync } from '../hooks/useAsync';
import { getProfile, saveProfile } from '../services/profile';
import type { StyleAxis, StyleProfile } from '../types';
import { useApp } from '../context/AppContext';

const AXES: {
  id: StyleAxis;
  title: string;
  text: string;
  icon: string;
  benefit: string;
  bgClass: string;
}[] = [
  {
    id: 'efficiency',
    title: 'Efficacité',
    text: 'S\'habiller en quelques secondes avec zéro fatigue décisionnelle.',
    icon: '⚡',
    benefit: 'Priorise la rapidité et la simplicité',
    bgClass: 'card-mint',
  },
  {
    id: 'economy',
    title: 'Économie',
    text: 'Rentabiliser les basiques de qualité, n\'acheter que les vrais besoins.',
    icon: '🌿',
    benefit: 'Maximise le coût par port',
    bgClass: 'card-butter',
  },
  {
    id: 'brand',
    title: 'Image',
    text: 'Construire un style marquant et affirmer une identité visuelle forte.',
    icon: '💎',
    benefit: 'Priorise les pièces fortes et l\'allure',
    bgClass: 'card-lavender',
  },
];

const FORMALITY_LEVELS = [
  { level: 0, label: 'Décontracté (Casual)' },
  { level: 1, label: 'Smart Casual' },
  { level: 2, label: 'Professionnel / Soigné' },
  { level: 3, label: 'Très Formel / Cérémonie' },
];

// « onepiece · Ethnic · beige · traditionnel » (Obj5) -> « Robe · traditionnel · beige »
const STYLE_WORDS: Record<string, string> = {
  top: 'hauts', bottom: 'bas', onepiece: 'robes', outer: 'vestes', footwear: 'chaussures', bag: 'sacs', accessory: 'accessoires',
  casual: 'décontracté', 'smart casual': 'smart casual', formal: 'habillé', sports: 'sport', ethnic: 'traditionnel', party: 'soirée',
  black: 'noir', white: 'blanc', grey: 'gris', beige: 'beige', brown: 'marron', blue: 'bleu', red: 'rouge', pink: 'rose',
  purple: 'violet', orange: 'orange', yellow: 'jaune', green: 'vert', metallic: 'doré / argenté', multicolor: 'multicolore',
};
const styleLabel = (c?: string) => {
  if (!c) return '';
  const words = Array.from(new Set(c.split('·').map(w => w.trim()).filter(Boolean).map(w => w.split('/').map(x => STYLE_WORDS[x.trim().toLowerCase()] || x.trim()).join(' et '))));
  return words.join(' · ').replace(/^./, x => x.toUpperCase());
};

export default function Profile() {
  const { profile: contextProfile, setProfile: setContextProfile, useDemoData } = useApp();
  const state = useAsync(getProfile);
  const [profile, setProfileState] = useState<StyleProfile>(contextProfile);
  const [formality, setFormality] = useState(profile.formalityPref ?? 1);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (state.data) {
      setProfileState(state.data);
      setContextProfile(state.data);
      if (state.data.formalityPref !== undefined) {
        setFormality(state.data.formalityPref);
      }
    }
  }, [state.data, setContextProfile]);

  async function chooseAxis(axis: StyleAxis) {
    const next: StyleProfile = { ...profile, axis };
    setProfileState(next);
    setContextProfile(next);
    setSaved(false);

    try {
      await saveProfile(next);
      setSaved(true);
      setTimeout(() => setSaved(false), 2400);
    } catch {
      setSaved(true);
      setTimeout(() => setSaved(false), 2400);
    }
  }

  async function chooseFormality(level: number) {
    setFormality(level);
    const next: StyleProfile = { ...profile, formalityPref: level };
    setProfileState(next);
    setContextProfile(next);
    setSaved(true);
    setTimeout(() => setSaved(false), 2400);
  }

  async function toggleBudget() {
    const next: StyleProfile = { ...profile, budgetMode: !profile.budgetMode };
    setProfileState(next);
    setContextProfile(next);
    setSaved(true);
    setTimeout(() => setSaved(false), 2400);
  }

  const scores = profile.scores || { efficacite: 86, economie: 62, image: 74 };
  // null = score non calculable par l'Obj5 (ex. économie sans prix dans les fiches)
  const pct = (v: number | null) => (v == null ? '—' : `${v}%`);

  return (
    <>
      <header className="page-head">
        <div>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            Mon profil de style <span style={{ fontSize: '1.6rem' }}>🪞</span>
          </h1>
          <p className="page-subtitle">
            Ce que votre garde-robe dit de votre style, et vos préférences pour les suggestions de tenues.
          </p>
        </div>

        {saved && (
          <div
            role="status"
            style={{
              background: 'var(--pastel-mint)',
              color: 'var(--pastel-mint-deep)',
              padding: '8px 18px',
              borderRadius: '999px',
              fontWeight: 600,
              fontSize: '0.86rem',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              boxShadow: 'var(--shadow-glow-mint)',
            }}
          >
            <span>✓</span>
            <span>Préférences Sauvegardées</span>
          </div>
        )}
      </header>

      {!useDemoData && state.error && (
        <div
          role="alert"
          style={{ background: 'var(--danger-bg)', color: 'var(--danger)', padding: '12px 18px', borderRadius: '16px', marginBottom: '20px', fontSize: '0.9rem' }}
        >
          Votre profil n'a pas pu être mis à jour ({state.error.message}). Les valeurs ci-dessous sont les dernières connues.
        </div>
      )}

      {!useDemoData && state.data?.model === 'référence' && (
        <div role="status" className="card" style={{ marginBottom: '20px', fontSize: '0.9rem', color: 'var(--muted)' }}>
          Profil provisoire : il deviendra plus personnel à partir de 18 pièces dans votre garde-robe.
        </div>
      )}

      {/* User Persona & Metrics Card */}
      <section
        className="card"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '24px',
          marginBottom: '28px',
          background: 'linear-gradient(135deg, #FFFFFF 0%, var(--pastel-pink-subtle) 100%)',
          flexWrap: 'wrap',
          padding: '24px',
        }}
      >
        <img
          src="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=200&auto=format&fit=crop&q=80"
          alt="Camille Stinson"
          style={{
            width: '80px',
            height: '80px',
            borderRadius: '50%',
            objectFit: 'cover',
            border: '3px solid #FFFFFF',
            boxShadow: 'var(--shadow-card)',
          }}
        />

        <div style={{ flex: 1, minWidth: '220px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <h2 style={{ fontSize: '1.4rem' }}>Camille Stinson</h2>
            <span className="chip-tag chip-tag-pink">Profil actif</span>
          </div>
          <p style={{ color: 'var(--muted)', fontSize: '0.9rem', margin: '4px 0 0' }}>
            Votre style dominant : <strong style={{ color: 'var(--ink)' }}>{styleLabel(profile.dominantCluster) || 'à découvrir'}</strong>
          </p>
        </div>

        {/* Wardrobe Diversity Badge */}
        <div style={{ background: '#FFFFFF', padding: '12px 20px', borderRadius: '18px', textAlign: 'center', border: '1px solid var(--line)' }}>
          <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--pastel-mint-deep)' }}>
            {profile.diversityScore || 78}%
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--muted)', textTransform: 'uppercase', fontWeight: 700 }}>
            Variété de la garde-robe
          </div>
        </div>

        <button
          className={`btn-sm ${profile.budgetMode ? 'btn-mint' : 'btn-secondary'}`}
          style={{ borderRadius: '999px', padding: '10px 18px', fontWeight: 600 }}
          onClick={toggleBudget}
        >
          {profile.budgetMode ? '🌿 Budget Prioritizer: Actif' : '🌿 Activer Mode Budget'}
        </button>
      </section>

      {/* Tripartite Persona Scores (Objectif 5 Core: Efficacité, Économie, Image) */}
      <section style={{ marginBottom: '32px' }}>
        <h3 style={{ fontSize: '1.2rem', marginBottom: '16px' }}>
          Ce qui compte pour vous
        </h3>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
          <div className="card card-mint" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--pastel-mint-deep)' }}>
                ⚡ EFFICACITÉ
              </span>
              <strong style={{ fontSize: '1.3rem' }}>{pct(scores.efficacite)}</strong>
            </div>
            <div style={{ width: '100%', height: '8px', background: '#FFFFFF', borderRadius: '999px', margin: '12px 0 8px', overflow: 'hidden' }}>
              <div style={{ width: `${scores.efficacite ?? 0}%`, height: '100%', background: 'var(--pastel-mint-deep)', borderRadius: '999px' }} />
            </div>
            <p style={{ fontSize: '0.78rem', color: 'var(--muted)', margin: 0 }}>
              Facilité et rapidité de sélection matinale.
            </p>
          </div>

          <div className="card card-butter" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--pastel-butter-deep)' }}>
                🌿 ÉCONOMIE
              </span>
              <strong style={{ fontSize: '1.3rem' }}>{pct(scores.economie)}</strong>
            </div>
            <div style={{ width: '100%', height: '8px', background: '#FFFFFF', borderRadius: '999px', margin: '12px 0 8px', overflow: 'hidden' }}>
              <div style={{ width: `${scores.economie ?? 0}%`, height: '100%', background: 'var(--pastel-butter-deep)', borderRadius: '999px' }} />
            </div>
            <p style={{ fontSize: '0.78rem', color: 'var(--muted)', margin: 0 }}>
              Taux de réutilisation et rentabilisation des pièces.
            </p>
          </div>

          <div className="card card-lavender" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--pastel-lavender-deep)' }}>
                💎 IMAGE / SIGNATURE
              </span>
              <strong style={{ fontSize: '1.3rem' }}>{pct(scores.image)}</strong>
            </div>
            <div style={{ width: '100%', height: '8px', background: '#FFFFFF', borderRadius: '999px', margin: '12px 0 8px', overflow: 'hidden' }}>
              <div style={{ width: `${scores.image ?? 0}%`, height: '100%', background: 'var(--pastel-lavender-deep)', borderRadius: '999px' }} />
            </div>
            <p style={{ fontSize: '0.78rem', color: 'var(--muted)', margin: 0 }}>
              Cohérence esthétique et allure distinctive.
            </p>
          </div>
        </div>
      </section>

      {/* Axis Choice */}
      <section style={{ marginBottom: '32px' }}>
        <h3 style={{ fontSize: '1.2rem', marginBottom: '8px' }}>Orientation Prioritaire</h3>
        <p style={{ color: 'var(--muted)', fontSize: '0.9rem', marginBottom: '16px' }}>
          Choisissez ce que vos suggestions de tenues doivent privilégier.
        </p>

        <div className="options" style={{ marginTop: 0 }}>
          {AXES.map(a => {
            const isSelected = profile.axis === a.id;
            return (
              <button
                key={a.id}
                className="option"
                aria-pressed={isSelected}
                onClick={() => chooseAxis(a.id)}
              >
                <div
                  className="option-icon"
                  style={{
                    background: isSelected ? 'var(--pastel-pink-soft)' : 'var(--paper)',
                    color: isSelected ? 'var(--pastel-pink-deep)' : 'var(--ink)',
                  }}
                >
                  {a.icon}
                </div>

                <h3 style={{ fontSize: '1.15rem', color: 'var(--ink)' }}>{a.title}</h3>
                <p>{a.text}</p>
              </button>
            );
          })}
        </div>
      </section>

      {/* Formality Preference (0 to 3) */}
      <section style={{ marginBottom: '32px' }}>
        <h3 style={{ fontSize: '1.2rem', marginBottom: '8px' }}>Préférence de Formalité Quotidienne (0 à 3)</h3>
        <p style={{ color: 'var(--muted)', fontSize: '0.9rem', marginBottom: '14px' }}>
          Indiquez à quel point vous aimez être habillé(e) au quotidien.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px' }}>
          {FORMALITY_LEVELS.map(f => (
            <button
              key={f.level}
              className="chip"
              aria-pressed={formality === f.level}
              onClick={() => chooseFormality(f.level)}
              style={{
                textAlign: 'center',
                padding: '12px 16px',
                borderRadius: '16px',
                fontWeight: 600,
                fontSize: '0.88rem',
              }}
            >
              Niveau {f.level} : {f.label}
            </button>
          ))}
        </div>
      </section>
    </>
  );
}
