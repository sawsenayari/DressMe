import { useState } from 'react';
import { login, register } from '../services/auth';
import { useApp } from '../context/AppContext';

/** Connexion / création de compte : chaque compte a sa propre garde-robe. */
export default function Auth() {
  const { setUser } = useApp();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (mode === 'register' && password !== confirm) { setError('Les deux mots de passe ne sont pas identiques.'); return; }
    setBusy(true);
    try {
      setUser(mode === 'login' ? await login(email, password) : await register(name, email, password));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally { setBusy(false); }
  };

  const field = { width: '100%' } as const;
  const label = { fontSize: '0.82rem', fontWeight: 600, display: 'block', marginBottom: '4px' } as const;

  return (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', padding: '24px 16px',
                  background: 'linear-gradient(135deg, var(--pastel-pink-subtle) 0%, var(--paper) 60%)' }}>
      <div className="card" style={{ width: '100%', maxWidth: '420px', background: '#FFFFFF', padding: '28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
          <div className="brand-icon">✨</div>
          <div>
            <div className="brand-title">DressMe</div>
            <div className="brand-subtitle">Studio de style</div>
          </div>
        </div>
        <h1 style={{ fontSize: '1.5rem', margin: '14px 0 4px' }}>{mode === 'login' ? 'Connexion' : 'Créer un compte'}</h1>
        <p style={{ color: 'var(--muted)', fontSize: '0.88rem', margin: '0 0 18px' }}>
          {mode === 'login' ? 'Retrouvez votre garde-robe et vos tenues.' : 'Votre garde-robe personnelle, visible par vous seul(e).'}
        </p>

        <div className="chips" role="tablist" aria-label="Connexion ou inscription" style={{ marginBottom: '16px' }}>
          {([['login', 'Se connecter'], ['register', 'Créer un compte']] as const).map(([m, l]) => (
            <button key={m} type="button" role="tab" className="chip" aria-selected={mode === m} aria-pressed={mode === m}
                    onClick={() => { setMode(m); setError(''); }}>{l}</button>
          ))}
        </div>

        {error && (
          <div role="alert" style={{ padding: '10px 14px', borderRadius: '12px', background: 'var(--danger-bg)', color: 'var(--danger)', fontSize: '0.85rem', marginBottom: '14px' }}>
            {error}
          </div>
        )}

        <form onSubmit={submit} style={{ display: 'grid', gap: '12px' }}>
          {mode === 'register' && (
            <div>
              <label htmlFor="auth-name" style={label}>Nom</label>
              <input id="auth-name" className="form-input" style={field} value={name} onChange={e => setName(e.target.value)}
                     autoComplete="name" required maxLength={60} />
            </div>
          )}
          <div>
            <label htmlFor="auth-email" style={label}>Adresse e-mail</label>
            <input id="auth-email" className="form-input" style={field} type="email" value={email} onChange={e => setEmail(e.target.value)}
                   autoComplete="email" required />
          </div>
          <div>
            <label htmlFor="auth-password" style={label}>Mot de passe{mode === 'register' ? ' (8 caractères au moins)' : ''}</label>
            <input id="auth-password" className="form-input" style={field} type="password" value={password} onChange={e => setPassword(e.target.value)}
                   autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required minLength={mode === 'register' ? 8 : undefined} />
          </div>
          {mode === 'register' && (
            <div>
              <label htmlFor="auth-confirm" style={label}>Confirmer le mot de passe</label>
              <input id="auth-confirm" className="form-input" style={field} type="password" value={confirm} onChange={e => setConfirm(e.target.value)}
                     autoComplete="new-password" required />
            </div>
          )}
          <button type="submit" className="btn" disabled={busy} style={{ marginTop: '6px' }}>
            {busy ? 'Un instant…' : mode === 'login' ? 'Se connecter' : 'Créer mon compte'}
          </button>
        </form>
      </div>
    </div>
  );
}
