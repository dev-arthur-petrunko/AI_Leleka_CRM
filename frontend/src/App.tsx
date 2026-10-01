import { useEffect, useState } from 'react';
import { Link, Route, Routes, useNavigate } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Deals from './pages/Deals';
import FeedHub from './pages/FeedHub';
import Orders from './pages/Orders';
import { login, token } from './api';

function useTheme() {
  const [theme, setTheme] = useState<'dark' | 'light'>(() =>
    matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark',
  );
  useEffect(() => {
    document.documentElement.dataset.theme = theme === 'light' ? 'light' : '';
  }, [theme]);
  return { theme, toggle: () => setTheme((t) => (t === 'dark' ? 'light' : 'dark')) };
}

function Login() {
  const nav = useNavigate();
  const [email, setEmail] = useState('owner@demo.ua');
  const [password, setPassword] = useState('123456789');
  const [err, setErr] = useState('');
  return (
    <div className="glass" style={{ maxWidth: 380, margin: '12vh auto', padding: 28 }}>
      <h2>Вхід у Leleka CRM</h2>
      <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email"
        style={inputStyle} />
      <input value={password} onChange={(e) => setPassword(e.target.value)} type="password"
        placeholder="пароль" style={inputStyle} />
      <button style={btnStyle} onClick={() => login(email, password).then(() => nav('/')).catch((e) => setErr(String(e)))}>
        Увійти
      </button>
      {err && <p style={{ color: 'var(--bad)' }}>{err}</p>}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: 12, marginBottom: 10, borderRadius: 10,
  border: '1px solid var(--glass-border)', background: 'transparent', color: 'var(--text)',
};
const btnStyle: React.CSSProperties = {
  width: '100%', padding: 13, borderRadius: 12, border: 'none', fontWeight: 700,
  background: 'linear-gradient(135deg, var(--accent-a), var(--accent-b))', color: '#fff', cursor: 'pointer',
};

function Palette({ onClose }: { onClose: () => void }) {
  const [q, setQ] = useState('');
  const [res, setRes] = useState<{ clients: any[]; deals: any[] }>({ clients: [], deals: [] });
  useEffect(() => {
    if (q.length < 2) { setRes({ clients: [], deals: [] }); return; }
    const t = setTimeout(async () => {
      const [c, d] = await Promise.all([
        import('./api').then((m) => m.api<{ items: any[] }>(`/clients?q=${encodeURIComponent(q)}&limit=5`)),
        import('./api').then((m) => m.api<{ items: any[] }>(`/deals?limit=50`)),
      ]);
      setRes({ clients: c?.items || [], deals: (d?.items || []).slice(0, 5) });
    }, 250);
    return () => clearTimeout(t);
  }, [q]);
  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', zIndex: 50, display: 'flex', justifyContent: 'center', paddingTop: '12vh' }}>
      <div className="glass" onClick={(e) => e.stopPropagation()} style={{ width: 480, maxWidth: '92vw', height: 'fit-content', padding: 16 }}>
        <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Клієнти, угоди, дії… (Esc — закрити)"
          style={{ width: '100%', padding: 12, borderRadius: 10 }} onKeyDown={(e) => e.key === 'Escape' && onClose()} />
        {res.clients.map((c: any) => <div key={c.id} style={{ padding: '6px 0' }}>👤 {c.name} · {c.phone || ''}</div>)}
        {res.deals.map((d: any) => <div key={d.id} style={{ padding: '6px 0' }}>🤝 {d.title} · {d.stage}</div>)}
      </div>
    </div>
  );
}

export default function App() {
  const { theme, toggle } = useTheme();
  const authed = !!token();
  const [palette, setPalette] = useState(false);
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setPalette((v) => !v);
      }
    };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, []);
  return (
    <>
      <div className="auroras"><span /><span /><span /></div>
      <header className="glass" style={{ position: 'sticky', top: 0, zIndex: 20, margin: 12, padding: '12px 20px', display: 'flex', gap: 18, alignItems: 'center' }}>
        <b>◈ Leleka</b>
        <Link to="/">Дашборд</Link>
        <Link to="/orders">Замовлення</Link>
        <Link to="/deals">Угоди</Link>
        <Link to="/feedhub">Feed Hub</Link>
        <span style={{ flex: 1 }} />
        <button onClick={() => setPalette(true)} title="Пошук (Ctrl+K)">⌘K</button>
        <button onClick={toggle} title="Тема">{theme === 'dark' ? '◐' : '◑'}</button>
        {!authed && <Link to="/login">Увійти</Link>}
      </header>
      <main style={{ maxWidth: 1200, margin: '0 auto', padding: '0 16px 40px' }}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/orders" element={<Orders />} />
          <Route path="/deals" element={<Deals />} />
          <Route path="/feedhub" element={<FeedHub />} />
          <Route path="/login" element={<Login />} />
        </Routes>
        {palette && <Palette onClose={() => setPalette(false)} />}
      </main>
    </>
  );
}
