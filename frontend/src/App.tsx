import { Suspense, lazy, useEffect, useState } from 'react';
import { Link, NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import {
  BarChart3, Bell, CheckSquare, ChevronLeft, ChevronRight, Crown, Ellipsis, Home, Inbox, KanbanSquare,
  Moon, Package, Plug, Search, Settings as SettingsIcon, ShoppingCart, Sun, Users, Plus, Zap,
} from 'lucide-react';
import Deals from './pages/Deals';
import FeedHub from './pages/FeedHub';
import Orders from './pages/Orders';
import Today from './pages/Today';
import Clients from './pages/Clients';
import InboxPage from './pages/InboxPage';
import TasksPage from './pages/TasksPage';
// Recharts їде окремим чанком — аналітика вантажиться ліниво
const Analytics = lazy(() => import('./pages/Analytics'));import IntegrationsPage from './pages/IntegrationsPage';
import SettingsPage from './pages/SettingsPage';
import UiKit from './pages/UiKit';
import PasswordPage from './pages/PasswordPage';
import AutomationsPage from './pages/AutomationsPage';
import BillingPage from './pages/BillingPage';
import NotificationsPage from './pages/NotificationsPage';
import logoMark from './assets/brand/logo-mark.png';
import { login, token } from './api';
import { applyTheme, loadMode, resolveTheme, saveMode, ThemeMode } from './theme';
import { t } from './i18n';

const NAV = [
  { to: '/', label: t('nav.today'), icon: Home, badge: null },
  { to: '/inbox', label: t('nav.inbox'), icon: Inbox, badge: 'inbox' },
  { to: '/deals', label: t('nav.deals'), icon: KanbanSquare, badge: null },
  { to: '/orders', label: t('nav.orders'), icon: ShoppingCart, badge: 'orders' },
  { to: '/clients', label: t('nav.clients'), icon: Users, badge: null },
  { to: '/tasks', label: t('nav.tasks'), icon: CheckSquare, badge: 'tasks' },
  { to: '/products', label: t('nav.products'), icon: Package, badge: null },
  { to: '/analytics', label: t('nav.analytics'), icon: BarChart3, badge: null },
  { to: '/automations', label: t('nav.automations'), icon: Zap, badge: null },
  { to: '/billing', label: t('nav.billing'), icon: Crown, badge: null },
  { to: '/integrations', label: t('nav.integrations'), icon: Plug, badge: 'integrations' },
  { to: '/settings', label: t('nav.settings'), icon: SettingsIcon, badge: null },
];
const CRUMBS: Record<string, string> = {
  '': 'Головна', inbox: 'Вхідні', deals: 'Угоди', orders: 'Замовлення', clients: 'Клієнти',
  tasks: 'Завдання', products: 'Товари', feedhub: 'Товари', analytics: 'Аналітика',
  integrations: 'Інтеграції', settings: 'Налаштування', login: 'Вхід', 'ui-kit': 'UI-kit',
  password: 'Безпека', automations: 'Автоматизації', billing: 'Тариф',
  notifications: 'Сповіщення',
};
const isMac = typeof navigator !== 'undefined' && /mac/i.test(navigator.platform);

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
      try {
        const { api: call } = await import('./api');
        const r = await call<{ clients: any[]; deals: any[]; orders: any[] }>(
          `/search?q=${encodeURIComponent(q)}`);
        if (r) setRes({ clients: r.clients || [], deals: r.deals || [], orders: r.orders || [] });
      } catch { /* помилка пошуку — тихо ігноруємо, список лишається порожнім */ }
    }, 250);
    return () => clearTimeout(tm);
  }, [q]);
  const go = (to: string) => { onClose(); nav(to); };
  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', zIndex: 50, display: 'flex', justifyContent: 'center', paddingTop: '12vh' }}>
      <div className="glass" onClick={(e) => e.stopPropagation()} style={{ width: 520, maxWidth: '92vw', height: 'fit-content', padding: 16 }}>
        <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Клієнти, угоди, замовлення… (Esc)"
          style={{ width: '100%', padding: 12, borderRadius: 10 }} onKeyDown={(e) => e.key === 'Escape' && onClose()} />
        {res.clients.map((c: any) => <div key={c.id} onClick={() => go('/clients')} style={{ padding: '6px 0', cursor: 'pointer' }}>Клієнт: {c.name} · {c.phone || ''}</div>)}
        {res.deals.map((d: any) => <div key={d.id} onClick={() => go('/deals')} style={{ padding: '6px 0', cursor: 'pointer' }}>Угода: {d.title}</div>)}
        {res.orders.map((o: any) => <div key={o.id} onClick={() => go('/orders')} style={{ padding: '6px 0', cursor: 'pointer' }}>Замовлення: {o.number}</div>)}
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
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('owner@demo.ua');
  const [password, setPassword] = useState('123456789');
  const [company, setCompany] = useState(() => {
    try { return localStorage.getItem('leleka.company') || ''; } catch { return ''; }
  });
  const [totp, setTotp] = useState('');
  const [ownerName, setOwnerName] = useState('');
  const [slug, setSlug] = useState('');
  const [confirmTok, setConfirmTok] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit() {
    setErr('');
    setBusy(true);
    try {
      if (mode === 'login') {
        await login(email, password, company, totp);
        try { localStorage.setItem('leleka.company', company); } catch { /* ignore */ }
      } else {
        const { register: reg } = await import('./api');
        await reg(email, password, ownerName || email, slug || email.split('@')[0]);
        try { localStorage.setItem('leleka.company', slug); } catch { /* ignore */ }
      }
      nav('/');
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  // Вхід в один клік всередині Telegram Mini App (initData перевіряє сервер)
  useEffect(() => {
    (async () => {
      const w = window as unknown as { Telegram?: { WebApp?: { initData?: string } } };
      const initData = w.Telegram?.WebApp?.initData;
      if (!initData || token()) return;
      try {
        const r = await fetch('/auth/telegram', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ init_data: initData }),
        });
        if (r.ok) {
          const j = await r.json();
          localStorage.setItem('leleka-token', j.access_token);
          if (j.refresh_token) localStorage.setItem('leleka-refresh', j.refresh_token);
          nav('/');
        }
      } catch { /* немає бота/токена — звичайний вхід */ }
    })();
  }, [nav]);
  return (
    <div className="glass" style={{ maxWidth: 380, margin: '10vh auto', padding: 28 }}>
      <h2>{mode === 'login' ? 'Вхід у Leleka CRM' : 'Нова компанія'}</h2>
      {mode === 'register' && (
        <>
          <input value={ownerName} onChange={(e) => setOwnerName(e.target.value)} placeholder="Ваше імʼя" style={inputStyle} />
          <input value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="ID компанії (латиницею)" style={inputStyle} />
        </>
      )}
      <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email" style={inputStyle} />
      <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" placeholder={mode === 'register' ? 'пароль (мін. 10 символів)' : 'пароль'} style={inputStyle} />
      {mode === 'login' && (
        <>
          <input value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Компанія (якщо email у кількох)" style={inputStyle} />
          <input value={totp} onChange={(e) => setTotp(e.target.value)} placeholder="Код 2FA (якщо увімкнено)" inputMode="numeric" style={inputStyle} />
        </>
      )}
      <button style={btnStyle} disabled={busy} onClick={submit}>
        {busy ? 'Зачекайте…' : mode === 'login' ? 'Увійти' : 'Створити компанію'}
      </button>
      <button onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setErr(''); }}
        style={{ ...btnStyle, background: 'transparent', color: 'var(--link)', marginTop: 8 }}>
        {mode === 'login' ? 'Немає компанії? Зареєструватись' : 'Уже є акаунт? Увійти'}
      </button>
      {mode === 'register' && (
        <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          Після реєстрації підтвердіть пошту токеном з листа (24 год).
        </p>
      )}
      <details style={{ marginTop: 8, fontSize: 13 }}>
        <summary style={{ cursor: 'pointer', color: 'var(--link)' }}>У мене є токен підтвердження пошти</summary>
        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <input value={confirmTok} onChange={(e) => setConfirmTok(e.target.value)}
            placeholder="Токен з листа" style={inputStyle} />
          <button style={{ ...btnStyle, width: 'auto' }} disabled={busy || !confirmTok.trim()}
            onClick={async () => {
              setErr('');
              try {
                const { API_BASE } = await import('./api');
                const r = await fetch(`${API_BASE}/auth/confirm-email`, {
                  method: 'POST', headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ token: confirmTok.trim() }),
                });
                if (!r.ok) throw new Error(`HTTP ${r.status}`);
                setConfirmTok('');
                setErr('');
              } catch {
                setErr('Токен невалідний або прострочений.');
              }
            }}>
            OK
          </button>
        </div>
      </details>
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
  const [collapsed, setCollapsedState] = useState<boolean>(() => {
    try {
      const v = localStorage.getItem('leleka.sidebar');
      if (v) return v === '1';
    } catch { /* ignore */ }
    return typeof window !== 'undefined' ? window.innerWidth < 1024 && window.innerWidth >= 768 : false;
  });
  const [badges, setBadges] = useState<Record<string, number | boolean>>({});
  const [me, setMe] = useState<any>(null);
  function setCollapsed(v: boolean) {
    setCollapsedState(v);
    try { localStorage.setItem('leleka.sidebar', v ? '1' : '0'); } catch { /* ignore */ }
    import('./api').then(({ api }) => api('/auth/me/preferences', {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ preferences: { sidebar_collapsed: v } }),
    }).catch(() => {}));
  }
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b') { e.preventDefault(); setCollapsed(!collapsed); }
    };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [collapsed]);
  useEffect(() => {
    (async () => {
      try {
        const { api } = await import('./api');
        const safe = <T,>(p: Promise<T | null>): Promise<T | null> => p.catch(() => null);
        const [tasks, convs, orders, integ, meResp, notifs] = await Promise.all([
          safe(api<any[]>('/tasks?status=open&limit=200')), safe(api<any[]>('/inbox/conversations?limit=100')),
          safe(api<{ items: any[] }>('/orders?status=new&limit=100')), safe(api<any[]>('/integrations')),
          safe(api<any>('/auth/me')), safe(api<any[]>('/notifications')),
        ]);
        const now = Date.now();
        setBadges({
          tasks: (tasks || []).filter((x: any) => x.due_at && new Date(x.due_at).getTime() < now).length,
          inbox: (convs || []).length,
          orders: (orders?.items || []).length,
          integrations: (integ || []).some((x: any) => x.status && x.status !== 'ok'),
          notifications: (notifs || []).length,
        });
      if (meResp) setMe(meResp);
      try {
        const { applyAnim } = await import('./theme');
        const srv = (meResp as any)?.preferences?.animations;
        if (srv === 'all' || srv === 'min' || srv === 'off') applyAnim(srv);
        else {
          const { loadAnim } = await import('./theme');
          applyAnim(loadAnim());
        }
      } catch { /* ignore */ }
      } catch { /* без звʼязку бейджі лишаються порожніми */ }
    })();
  }, [loc.pathname]);
  return (
    <>
      <div style={{ display: 'flex', minHeight: '100vh' }}>
        <aside className="glass sidebar" aria-label="Головне меню"
          style={{ width: collapsed ? 64 : 240, margin: 12, padding: 14,
            display: 'flex', flexDirection: 'column', gap: 2, position: 'sticky', top: 12,
            height: 'calc(100vh - 24px)', transition: 'width var(--dur-200,200ms) var(--ease-out, ease-out)',
            overflow: 'hidden' }}>
          <Link to="/" style={{ display: 'flex', gap: 10, alignItems: 'center',
            padding: '6px 10px 14px', color: 'var(--text)', textDecoration: 'none' }}>
            <img src={logoMark} alt="AI Leleka CRM" width={30} height={30}
              style={{ borderRadius: 8, flex: 'none' }} />
            {!collapsed && <b>AI Leleka CRM</b>}
          </Link>
          {NAV.map(({ to, label, icon: Icon, badge }) => {
            const n = badge ? Number(badges[badge] || 0) : 0;
            const dot = badge === 'integrations' && badges[badge] === true;
            return (
              <NavLink key={to} to={to} title={label}
                style={({ isActive }) => ({
                  display: 'flex', gap: 10, alignItems: 'center', padding: '10px 12px', borderRadius: 10,
                  color: isActive ? 'var(--primary)' : 'var(--text)', textDecoration: 'none',
                  background: isActive ? 'var(--bg-hover)' : 'transparent',
                  fontWeight: isActive ? 700 : 400, whiteSpace: 'nowrap', position: 'relative',
                })}>
                <Icon size={18} aria-hidden />
                {!collapsed && label}
                {badge && (n > 0 || dot) && (
                  collapsed
                    ? <span aria-label={`${label}: ${n || 'помилка'}`}
                        style={{ position: 'absolute', top: 6, right: 6, minWidth: 16, height: 16,
                          borderRadius: 8, background: 'var(--danger)', color: 'var(--primary-fg)',
                          fontSize: 10, fontWeight: 700, display: 'flex', alignItems: 'center',
                          justifyContent: 'center', padding: '0 4px' }}>
                        {dot ? '' : n > 9 ? '9+' : n}</span>
                    : <span style={{ marginLeft: 'auto', minWidth: 20, height: 20, borderRadius: 10,
                        background: badge === 'tasks' ? 'var(--danger)' : 'var(--primary)',
                        color: 'var(--primary-fg)', fontSize: 11, fontWeight: 700, display: 'inline-flex',
                        alignItems: 'center', justifyContent: 'center', padding: '0 6px' }}>
                        {dot ? '!' : n > 99 ? '99+' : n}</span>
                )}
              </NavLink>
            );
          })}
          <div style={{ flex: 1 }} />
          {!collapsed && me && (
            <div style={{ fontSize: 12, color: 'var(--text-muted)', padding: '8px 10px',
              borderTop: '1px solid var(--border)' }}>
              <div style={{ fontWeight: 700, color: 'var(--text)' }}>{me.full_name || me.email}</div>
              <div>{me.role}</div>
            </div>
          )}
          {!collapsed && (
            <Link to="/settings" style={{ fontSize: 12, color: 'var(--link)', padding: '4px 10px' }}>
              Допомога
            </Link>
          )}
          <button onClick={() => setCollapsed(!collapsed)}
            aria-expanded={!collapsed} aria-controls="sidebar" aria-label="Згорнути меню (Ctrl+B)"
            title="Згорнути меню (Ctrl+B)"
            style={{ background: 'transparent', border: '1px solid var(--border)', color: 'var(--text)',
              borderRadius: 10, padding: 8, cursor: 'pointer', display: 'flex',
              alignItems: 'center', justifyContent: 'center', gap: 6 }}>
            {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>
        </aside>
        <div style={{ flex: 1, minWidth: 0 }}>
          <header className="glass" style={{ margin: '12px 12px 0', padding: '10px 16px', display: 'flex', gap: 10, alignItems: 'center' }}>
            <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>
              {['Головна', ...crumbs.map((c) => CRUMBS[c] || c)].join(' / ')}
            </span>
            <span style={{ flex: 1 }} />
            <button onClick={() => setPalette(true)} aria-label={isMac ? 'Пошук (⌘K)' : 'Пошук (Ctrl K)'}
              title={isMac ? '⌘K' : 'Ctrl K'} style={iconBtn}>
              <Search size={18} aria-hidden />
            </button>
            <CreateMenu />
            <Link to="/notifications" aria-label="Сповіщення" title="Сповіщення"
              style={{ ...iconBtn, position: 'relative', textDecoration: 'none' }}>
              <Bell size={18} aria-hidden />
              {Number(badges.notifications || 0) > 0 && (
                <span aria-hidden className="pulse-dot"
                  style={{ position: 'absolute', top: 8, right: 8, minWidth: 16, height: 16,
                    borderRadius: 8, background: 'var(--danger)', color: 'var(--primary-fg)',
                    fontSize: 10, fontWeight: 700, display: 'flex', alignItems: 'center',
                    justifyContent: 'center', padding: '0 4px' }}>
                  {Number(badges.notifications) > 9 ? '9+' : badges.notifications}
                </span>
              )}
            </Link>
            <button onClick={() => setMode(mode === 'evening' ? 'morning' : 'evening')}
              aria-label="Тема" title={`${t('theme.morning')} / ${t('theme.evening')} / ${t('theme.auto')}`} style={iconBtn}>
              {mode === 'evening' ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            {!authed && <Link to="/login">Увійти</Link>}
          </header>
          <main key={loc.pathname} className="page-in" style={{ maxWidth: 1440, margin: '0 auto', padding: '16px 16px 90px' }}>
            {!authed && loc.pathname !== '/login' ? (
              <Navigate to="/login" replace />
            ) : me?.must_change_password && !['/password', '/login'].includes(loc.pathname) ? (
              <Navigate to="/password" replace />
            ) : (
            <Routes>
              <Route path="/" element={<Today />} />
              <Route path="/deals" element={<Deals />} />
              <Route path="/orders" element={<Orders />} />
              <Route path="/feedhub" element={<FeedHub />} />
              <Route path="/products" element={<FeedHub />} />
              <Route path="/clients" element={<Clients />} />
              <Route path="/inbox" element={<InboxPage />} />
              <Route path="/tasks" element={<TasksPage />} />
              <Route path="/analytics" element={
                <Suspense fallback={<div className="glass" style={{ padding: 28 }}>Завантаження…</div>}>
                  <Analytics />
                </Suspense>
              } />
              <Route path="/integrations" element={<IntegrationsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/ui-kit" element={<UiKit />} />
              <Route path="/password" element={<PasswordPage />} />
              <Route path="/automations" element={<AutomationsPage />} />
              <Route path="/billing" element={<BillingPage />} />
              <Route path="/notifications" element={<NotificationsPage />} />
              <Route path="/login" element={<Login />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
            )}
          </main>
        </div>
      </div>
      <nav className="mobilebar glass" style={{ position: 'fixed', bottom: 0, left: 0, right: 0, display: 'none', zIndex: 20 }}>
        {([
          ['/', 'Головна', Home], ['/deals', t('nav.deals'), KanbanSquare], ['/orders', t('nav.orders'), ShoppingCart],
          ['/inbox', t('nav.inbox'), Inbox], ['/settings', t('nav.more'), Ellipsis],
        ] as [string, string, typeof Home][]).map(([to, label, Icon]) => (
          <NavLink key={to} to={to}
            style={{ flex: 1, textAlign: 'center', padding: '8px 0 10px', fontSize: 10, color: 'var(--text-muted)', textDecoration: 'none' }}>
            <span style={{ display: 'flex', justifyContent: 'center' }}><Icon size={20} aria-hidden /></span>{label}
          </NavLink>
        ))}
      </nav>
      <style>{`@media(max-width:1023px){.sidebar{display:none!important}.mobilebar{display:flex!important}}`}</style>
      {palette && <Palette onClose={() => setPalette(false)} />}
    </>
  );
}
