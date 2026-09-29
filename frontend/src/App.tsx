import { useEffect, useState } from 'react';
import { Link, Route, Routes, useNavigate } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Deals from './pages/Deals';
import FeedHub from './pages/FeedHub';
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

export default function App() {
  const { theme, toggle } = useTheme();
  const authed = !!token();
  return (
    <>
      <div className="auroras"><span /><span /><span /></div>
      <header className="glass" style={{ position: 'sticky', top: 0, zIndex: 20, margin: 12, padding: '12px 20px', display: 'flex', gap: 18, alignItems: 'center' }}>
        <b>◈ Leleka</b>
        <Link to="/">Дашборд</Link>
        <Link to="/deals">Угоди</Link>
        <Link to="/feedhub">Feed Hub</Link>
        <span style={{ flex: 1 }} />
        <button onClick={toggle} title="Тема">{theme === 'dark' ? '◐' : '◑'}</button>
        {!authed && <Link to="/login">Увійти</Link>}
      </header>
      <main style={{ maxWidth: 1200, margin: '0 auto', padding: '0 16px 40px' }}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/deals" element={<Deals />} />
          <Route path="/feedhub" element={<FeedHub />} />
          <Route path="/login" element={<Login />} />
        </Routes>
      </main>
    </>
  );
}
