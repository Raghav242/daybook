import { useState, type FormEvent } from 'react';
import { BookOpen } from 'lucide-react';
import { api } from '../../shared/api/client';
import type { User } from '../../shared/api/contracts';

export function AuthScreen({ onSignedIn, message }: {onSignedIn: (user: User) => void; message: string}) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    setPending(true); setError('');
    try { const session = await api[mode](username, password); setPassword(''); onSignedIn(session.user); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not sign in.'); }
    finally { setPending(false); }
  }
  return <main className="auth-shell"><section className="auth-card" aria-labelledby="auth-title">
    <div className="brand"><span className="brand-mark"><BookOpen size={23} strokeWidth={1.5}/></span><span>daybook<span className="brand-caption">A place for your everyday.</span></span></div>
    <p className="eyebrow">YOUR OWN SPACE</p><h1 id="auth-title">{mode === 'login' ? 'Welcome back.' : 'Make room for your day.'}</h1>
    <p className="page-subtitle">{mode === 'login' ? 'Sign in to pick up where you left off.' : 'Create an account. Your Daybook starts fresh.'}</p>
    {message && <p role="status" className="form-hint">{message}</p>}
    <form onSubmit={submit}><fieldset disabled={pending}>
      <label htmlFor="auth-username">Username<input id="auth-username" name="username" autoComplete="username" autoCapitalize="none" spellCheck={false} required minLength={3} maxLength={40} pattern="[A-Za-z0-9_.\-]{3,40}" value={username} onChange={e => setUsername(e.target.value)} /></label>
      <label htmlFor="auth-password">Password<input id="auth-password" name="password" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required minLength={mode === 'register' ? 5 : 1} maxLength={128} value={password} onChange={e => setPassword(e.target.value)}/></label>
      {error && <p role="alert" className="error">{error}</p>}
      <button className="button primary auth-submit" type="submit">{pending ? 'One moment…' : mode === 'login' ? 'Sign in' : 'Create account'}</button>
    </fieldset></form>
    <p className="auth-switch">{mode === 'login' ? 'New to Daybook?' : 'Already have an account?'} <button className="text-button" disabled={pending} onClick={() => {setMode(mode === 'login' ? 'register' : 'login'); setError(''); setPassword('');}}>{mode === 'login' ? 'Create an account' : 'Sign in'}</button></p>
    <p className="muted auth-footnote">Less to remember. More room to live.</p>
  </section></main>;
}
