'use client';
import { FormEvent, useState } from 'react';
export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError('');
    try {
      const response = await fetch('/auth/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      if (!response.ok) {
        const result = await response.json();
        throw new Error(result.error || 'Não foi possível entrar');
      }
      window.location.assign('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha no login');
      setLoading(false);
    }
  }
  return (
    <main style={{ minHeight: '100svh', display: 'grid', placeItems: 'center', padding: 24, background: '#0c0e10' }}>
      <form onSubmit={submit} style={{ width: '100%', maxWidth: 410, padding: 36, border: '1px solid #c6aa7b55', background: '#121619', display: 'grid', gap: 18 }}>
        <span className="eyebrow">MOTOR ATLAS</span>
        <h1 style={{ fontSize: 42, margin: 0 }}>Acesso ao observatório</h1>
        <p style={{ color: '#999d9f', margin: 0 }}>Entre com sua conta autorizada.</p>
        <label style={{ display: 'grid', gap: 7 }}>E-mail
          <input aria-label="E-mail" autoComplete="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
            style={{ padding: 13, background: '#0c0e10', border: '1px solid #ffffff44', color: 'white' }} />
        </label>
        <label style={{ display: 'grid', gap: 7 }}>Senha
          <input aria-label="Senha" autoComplete="current-password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
            style={{ padding: 13, background: '#0c0e10', border: '1px solid #ffffff44', color: 'white' }} />
        </label>
        {error && <p role="alert" style={{ color: '#ffb6ae', margin: 0 }}>{error}</p>}
        <button disabled={loading} type="submit" className="primary" style={{ justifyContent: 'center', opacity: loading ? 0.6 : 1 }}>
          {loading ? 'Entrando...' : 'Entrar'}
        </button>
      </form>
    </main>
  );
}
