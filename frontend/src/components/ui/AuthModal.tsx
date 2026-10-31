import { useState } from 'react';
import { useApp } from '../../context/AppContext';

export function AuthModal() {
  const { isAuthModalOpen, setIsAuthModalOpen } = useApp();
  const [tab, setTab] = useState<'signin' | 'signup' | 'onboard'>('signin');
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');

  if (!isAuthModalOpen) return null;

  return (
    <div className="modal-backdrop" onClick={() => setIsAuthModalOpen(false)}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <button className="modal-close" onClick={() => setIsAuthModalOpen(false)} aria-label="Close modal">
          ✕
        </button>

        {/* Header Tabs */}
        <div style={{ display: 'flex', gap: '8px', marginBottom: '24px', borderBottom: '1px solid var(--line)', paddingBottom: '12px' }}>
          <button
            className={`chip ${tab === 'signin' ? 'active' : ''}`}
            aria-pressed={tab === 'signin'}
            onClick={() => setTab('signin')}
          >
            Sign In
          </button>
          <button
            className={`chip ${tab === 'signup' ? 'active' : ''}`}
            aria-pressed={tab === 'signup'}
            onClick={() => setTab('signup')}
          >
            Create Account
          </button>
          <button
            className={`chip ${tab === 'onboard' ? 'active' : ''}`}
            aria-pressed={tab === 'onboard'}
            onClick={() => setTab('onboard')}
          >
            ✨ Onboarding Tour
          </button>
        </div>

        {tab === 'signin' && (
          <div>
            <div style={{ textAlign: 'center', marginBottom: '24px' }}>
              <div
                style={{
                  width: '64px',
                  height: '64px',
                  borderRadius: '20px',
                  background: 'linear-gradient(135deg, var(--pastel-pink) 0%, var(--pastel-lavender) 100%)',
                  margin: '0 auto 14px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '28px',
                  boxShadow: 'var(--shadow-glow-pink)',
                }}
              >
                👗
              </div>
              <h2>Welcome back</h2>
              <p style={{ color: 'var(--muted)', fontSize: '0.9rem', marginTop: '4px' }}>
                Sign in to sync your wardrobe and get daily AI recommendations.
              </p>
            </div>

            <form onSubmit={e => { e.preventDefault(); setIsAuthModalOpen(false); }}>
              <div className="form-group">
                <label className="form-label">Email Address</label>
                <input
                  type="email"
                  className="form-input"
                  placeholder="camille@example.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Password</label>
                <input
                  type="password"
                  className="form-input"
                  placeholder="••••••••••••"
                  defaultValue="password123"
                  required
                />
              </div>

              <button type="submit" className="btn" style={{ width: '100%', marginTop: '12px' }}>
                Sign In to DressMe
              </button>
            </form>
          </div>
        )}

        {tab === 'signup' && (
          <div>
            <div style={{ textAlign: 'center', marginBottom: '24px' }}>
              <h2>Join DressMe</h2>
              <p style={{ color: 'var(--muted)', fontSize: '0.9rem', marginTop: '4px' }}>
                Curate your dream closet with personalized AI styling.
              </p>
            </div>

            <form onSubmit={e => { e.preventDefault(); setIsAuthModalOpen(false); }}>
              <div className="form-group">
                <label className="form-label">Full Name</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Camille Stinson"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Email Address</label>
                <input
                  type="email"
                  className="form-input"
                  placeholder="camille@example.com"
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Create Password</label>
                <input
                  type="password"
                  className="form-input"
                  placeholder="At least 8 characters"
                  required
                />
              </div>

              <button type="submit" className="btn btn-mint" style={{ width: '100%', marginTop: '12px' }}>
                Create Free Account
              </button>
            </form>
          </div>
        )}

        {tab === 'onboard' && (
          <div style={{ textAlign: 'center' }}>
            <div
              style={{
                borderRadius: '24px',
                background: 'linear-gradient(135deg, #FFF0F5 0%, #EDE4F8 100%)',
                padding: '28px 20px',
                marginBottom: '20px',
                border: '1px solid var(--pastel-pink)',
              }}
            >
              <div style={{ fontSize: '42px', marginBottom: '12px' }}>✨ 👒 👠</div>
              <h3 style={{ fontSize: '1.25rem', marginBottom: '8px' }}>Your Personal AI Wardrobe</h3>
              <p style={{ color: 'var(--muted)', fontSize: '0.88rem', margin: 0, lineHeight: 1.45 }}>
                1. Snap photos of your clothes to build your digital wardrobe.<br />
                2. Receive weather-tailored daily outfit combinations.<br />
                3. Scan clothes before buying to check compatibility score!
              </p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px', marginBottom: '24px' }}>
              <div style={{ background: 'var(--pastel-pink-soft)', padding: '12px', borderRadius: '16px' }}>
                <span style={{ fontSize: '20px' }}>📸</span>
                <div style={{ fontSize: '0.78rem', fontWeight: 600, marginTop: '4px' }}>Digitize</div>
              </div>
              <div style={{ background: 'var(--pastel-mint-soft)', padding: '12px', borderRadius: '16px' }}>
                <span style={{ fontSize: '20px' }}>🪄</span>
                <div style={{ fontSize: '0.78rem', fontWeight: 600, marginTop: '4px' }}>Generate</div>
              </div>
              <div style={{ background: 'var(--pastel-butter-soft)', padding: '12px', borderRadius: '16px' }}>
                <span style={{ fontSize: '20px' }}>🎯</span>
                <div style={{ fontSize: '0.78rem', fontWeight: 600, marginTop: '4px' }}>Match Score</div>
              </div>
            </div>

            <button className="btn" style={{ width: '100%' }} onClick={() => setIsAuthModalOpen(false)}>
              Got it, let's dress!
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
