import { useEffect, useState } from 'react';
import { Link, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import {
  BarChart3, Bell, Inbox, KanbanSquare, Moon, Package, Settings as SettingsIcon,
  ShoppingCart, Sun, Users, CheckSquare, Home, Plus,
} from 'lucide-react';
import Dashboard from './pages/Dashboard';
import Deals from './pages/Deals';
import FeedHub from './pages/FeedHub';
import Orders from './pages/Orders';
import Today from './pages/Today';
import Clients from './pages/Clients';
import InboxPage from './pages/InboxPage';
import TasksPage from './pages/TasksPage';
import Analytics from './pages/Analytics';
import IntegrationsPage from './pages/IntegrationsPage';
import SettingsPage from './pages/SettingsPage';
import UiKit from './pages/UiKit';
import { login, token } from './api';
import { applyTheme, loadMode, resolveTheme, saveMode, ThemeMode } from './theme';
import { t } from './i18n';

const NAV = [
  { to: '/', label: t('nav.today'), icon: Home },
  { to: '/inbox', label: t('nav.inbox'), icon: Inbox },
  { to: '/deals', label: t('nav.deals'), icon: KanbanSquare },
  { to: '/orders', label: t('nav.orders'), icon: ShoppingCart },
  { to: '/clients', label: t('nav.clients'), icon: Users },
  { to: '/tasks', label: t('nav.tasks'), icon: CheckSquare },
  { to: '/products', label: t('nav.products'), icon: Package },
  { to: '/analytics', label: t('nav.analytics'), icon: BarChart3 },
  { to: '/integrations', label: t('nav.integrations'), icon: SettingsIcon },
  { to: '/settings', label: t('nav.settings'), icon: SettingsIcon },
];
const MOBILE = ['/', '/deals', '/orders', '/inbox', '/more'];

function ThemeToggle({ mode, setMode }: { mode: ThemeMode; setMode: (m: ThemeMode) => void }) {
  const next = mode === 'evening' ? 'morning' : 'evening';
  return (
    <button aria-label="Тема" title={`${t('theme.morning')} / ${t('theme.evening')} / ${t('theme.auto')}`}
      onClick={() => setMode(next)} style={iconBtn}>
      {mode === 'evening' ? <Sun size={18} /> : <Moon size={18} />}
    </button>
  );
}

const iconBtn: React.CSSProperties = {
  background: 'transparent', border: '1px solid var(--border)', color: 'var(--text)',
  borderRadius: 10, width: 40, height: 40, display: 'inline-flex', alignItems: 'center',
  justifyContent: 'center', cursor: 'pointer',
};

function CreateMenu() {
  const [open, setOpen] = useState(false);
  const nav = useNavigate();
  const items: [string, string][] = [['/deals', 'Угода'], ['/orders', 'Замовлення'], ['/clients', 'Клієнт'], ['/tasks', 'Завдання']];
  return (
    <div style={{ position: 'relative' }}>
      <button onClick={() => setOpen((v) => !v)} aria-label={t('action.create')}
        style={{ background: 'var(--primary)', color: 'var(--primary-fg)', border: 'none',
          borderRadius: 10, padding: '10px 16px', fontWeight: 700, cursor: 'pointer',
          display: 'inline-flex', gap: 6, alignItems: 'center' }}>
        <Plus size={16} /> {t('action.create')}
      </button>
      {open && (
        <div className="glass" style={{ position: 'absolute', right: 0, top: 48, zIndex: 30, minWidth: 200, padding: 6 }}>
          {items.map(([to, label]) => (
            <div key={to}><Link to={to} onClick={() => setOpen(false)}
              style={{ display: 'block', padding: '10px 12px', borderRadius: 8, color: 'var(--text)', textDecoration: 'none' }}>
              {label}</Link></div>
          ))}
        </div>
      )}
    </div>
  );
}

function Palette({ onClose }: { onClose: () => void }) {
  const [q, setQ] = useState('');
  const [res, setRes] = useState<{ clients: any[]; deals: any[]; orders: any[] }>({ clients: [], deals: [], orders: [] });
  const nav = useNavigate();
  useEffect(() => {
    if (q.length < 2) return;
    const tm = setTimeout(async () => {
      const { api: call } = await import('./api');
      const r = await call<{ clients: any[]; deals: any[]; orders: any[] }>(
        `/search?q=${encodeURIComponent(q)}`);
      if (r) setRes({ clients: r.clients || [], deals: r.deals || [], orders: r.orders || [] });
    }, 250);
    return () => clearTimeout(tm);
  }, [q]);
  const go = (to: string) => { onClose(); nav(to); };
  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', zIndex: 50, display: 'flex', justifyContent: 'center', paddingTop: '12vh' }}>
      <div className="glass" onClick={(e) => e.stopPropagation()} style={{ width: 520, maxWidth: '92vw', height: 'fit-content', padding: 16 }}>
        <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Клієнти, угоди, замовлення… (Esc)"
          style={{ width: '100%', padding: 12, borderRadius: 10 }} onKeyDown={(e) => e.key === 'Escape' && onClose()} />
        {res.clients.map((c: any) => <div key={c.id} onClick={() => go('/clients')} style={{ padding: '6px 0', cursor: 'pointer' }}>👤 {c.name} · {c.phone || ''}</div>)}
        {res.deals.map((d: any) => <div key={d.id} onClick={() => go('/deals')} style={{ padding: '6px 0', cursor: 'pointer' }}>🤝 {d.title}</div>)}
        {res.orders.map((o: any) => <div key={o.id} onClick={() => go('/orders')} style={{ padding: '6px 0', cursor: 'pointer' }}>🧾 {o.number}</div>)}
        <div style={{ borderTop: '1px solid var(--border)', marginTop: 8, paddingTop: 8, color: 'var(--text-muted)', fontSize: 13 }}>
          <div onClick={() => go('/deals')} style={{ cursor: 'pointer', padding: '4px 0' }}>+ Створити угоду</div>
          <div onClick={() => go('/orders')} style={{ cursor: 'pointer', padding: '4px 0' }}>→ Перейти до Замовлень</div>
        </div>
      </div>
    </div>
  );
}

function Login() {
  const nav = useNavigate();
  const [email, setEmail] = useState('owner@demo.ua');
  const [password, setPassword] = useState('123456789');
  const [err, setErr] = useState('');
  return (
    <div className="glass" style={{ maxWidth: 380, margin: '12vh auto', padding: 28 }}>
      <h2>Вхід у Leleka CRM</h2>
      <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email" style={inputStyle} />
      <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" placeholder="пароль" style={inputStyle} />
      <button style={btnStyle} onClick={() => login(email, password).then(() => nav('/')).catch((e) => setErr(String(e)))}>Увійти</button>
      {err && <p style={{ color: 'var(--danger)' }}>{err}</p>}
    </div>
  );
}
const inputStyle: React.CSSProperties = { width: '100%', padding: 12, marginBottom: 10, borderRadius: 10, border: '1px solid var(--border)', background: 'var(--bg)', color: 'var(--text)' };
const btnStyle: React.CSSProperties = { width: '100%', padding: 13, borderRadius: 12, border: 'none', fontWeight: 700, background: 'var(--primary)', color: 'var(--primary-fg)', cursor: 'pointer' };

export default function App() {
  const [mode, setModeState] = useState<ThemeMode>(() => loadMode());
  const [palette, setPalette] = useState(false);
  const authed = !!token();
  const loc = useLocation();
  const setMode = (m: ThemeMode) => { setModeState(m); saveMode(m); applyTheme(resolveTheme(m)); };
  useEffect(() => { applyTheme(resolveTheme(loadMode())); }, []);
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setPalette((v) => !v); }
    };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, []);
  const crumbs = loc.pathname.split('/').filter(Boolean);
  return (
    <>
      <div className="auroras"><span /><span /><span /></div>
      <div style={{ display: 'flex', minHeight: '100vh' }}>
        <aside className="glass sidebar" style={{ width: 240, margin: 12, padding: 14, display: 'flex', flexDirection: 'column', gap: 2, position: 'sticky', top: 12, height: 'calc(100vh - 24px)' }}>
          <b style={{ padding: '6px 10px 14px' }}>◈ Leleka</b>
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} style={({ isActive }) => ({
              display: 'flex', gap: 10, alignItems: 'center', padding: '10px 12px', borderRadius: 10,
              color: isActive ? 'var(--link)' : 'var(--text)', textDecoration: 'none',
              background: isActive ? 'var(--bg-hover)' : 'transparent', fontWeight: isActive ? 700 : 400,
            })}>
              <Icon size={18} />{label}
            </NavLink>
          ))}
        </aside>
        <div style={{ flex: 1, minWidth: 0 }}>
          <header className="glass" style={{ margin: '12px 12px 0', padding: '10px 16px', display: 'flex', gap: 10, alignItems: 'center' }}>
            <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>Leleka{crumbs.map((c) => ` / ${c}`).join('')}</span>
            <span style={{ flex: 1 }} />
            <button onClick={() => setPalette(true)} aria-label="Пошук" style={iconBtn}>⌘K</button>
            <CreateMenu />
            <button aria-label="Сповіщення" style={iconBtn}><Bell size={18} /></button>
            <button onClick={() => setMode(mode === 'evening' ? 'morning' : 'evening')}
              aria-label="Тема" title={`${t('theme.morning')} / ${t('theme.evening')} / ${t('theme.auto')}`} style={iconBtn}>
              {mode === 'evening' ? '☀' : '◐'}
            </button>
            {!authed && <Link to="/login">Увійти</Link>}
          </header>
          <main style={{ maxWidth: 1440, margin: '0 auto', padding: '16px 16px 90px' }}>
            <Routes>
              <Route path="/" element={<Today />} />
              <Route path="/deals" element={<Deals />} />
              <Route path="/orders" element={<Orders />} />
              <Route path="/feedhub" element={<FeedHub />} />
              <Route path="/products" element={<FeedHub />} />
              <Route path="/clients" element={<Clients />} />
              <Route path="/inbox" element={<InboxPage />} />
              <Route path="/tasks" element={<TasksPage />} />
              <Route path="/analytics" element={<Analytics />} />
              <Route path="/integrations" element={<IntegrationsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/ui-kit" element={<UiKit />} />
              <Route path="/login" element={<Login />} />
            </Routes>
          </main>
        </div>
      </div>
      <nav className="mobilebar glass" style={{ position: 'fixed', bottom: 0, left: 0, right: 0, display: 'none', zIndex: 20 }}>
        {[['/', 'Головна', '◈'], ['/deals', t('nav.deals'), '▦'], ['/orders', t('nav.orders'), '🧾'],
          ['/inbox', t('nav.inbox'), '✉'], ['/more', t('nav.more'), '⋯']].map(([to, label, ico]) => (
          <NavLink key={to} to={to === '/more' ? '/settings' : to}
            style={{ flex: 1, textAlign: 'center', padding: '8px 0 10px', fontSize: 10, color: 'var(--text-muted)', textDecoration: 'none' }}>
            <span style={{ fontSize: 20, display: 'block' }}>{ico}</span>{label}
          </NavLink>
        ))}
      </nav>
      <style>{`@media(max-width:1023px){.sidebar{display:none!important}.mobilebar{display:flex!important}}`}</style>
      {palette && <Palette onClose={() => setPalette(false)} />}
    </>
  );
}
