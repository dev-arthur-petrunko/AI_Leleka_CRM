import { useEffect, useState } from 'react';
import { api } from '../api';

type Src = { id: string; name: string; last_status?: string; last_run_at?: string; interval_minutes: number };
type Run = { source_id?: string; source?: string; status: string; added?: number; updated?: number; removed?: number; started_at?: string; when?: string };

const dot: Record<string, string> = { ok: 'var(--ok)', error: 'var(--bad)', skipped: 'var(--warn)' };

export default function FeedHub() {
  const [sources, setSources] = useState<Src[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [products, setProducts] = useState<any[]>([]);
  const [msg, setMsg] = useState('');
  async function load() {
    const [s, r, p] = await Promise.all([
      api<Src[]>('/feedhub/sources'), api<Run[]>('/feedhub/runs?limit=10'), api<{ items: any[] }>('/feedhub/products?limit=50'),
    ]);
    if (s) setSources(s);
    if (r) setRuns(r);
    if (p) setProducts(p.items || []);
  }
  useEffect(() => { load(); }, []);
  async function refresh(id: string) {
    setMsg('Оновлення…');
    const r = await api<{ added: number; updated: number; removed: number; status: string }>(
      `/feedhub/sources/${id}/run`, { method: 'POST' });
    setMsg(r ? `Готово: +${r.added} ~${r.updated} −${r.removed}` : 'Демо: увійдіть, щоб запустити');
    load();
  }
  return (
    <div>
      <div className="glass" style={{ padding: 18, marginBottom: 14 }}>
        <h3>Джерела фідів</h3>
        {sources.length === 0 && <p style={{ color: 'var(--text-2)' }}>Порожньо — додайте перше джерело через API (POST /feedhub/sources).</p>}
        {sources.map((s) => (
          <div key={s.id} style={{ display: 'flex', gap: 10, alignItems: 'center', padding: '10px 0' }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: dot[s.last_status || ''] || 'var(--text-2)', boxShadow: `0 0 8px ${dot[s.last_status || ''] || 'transparent'}` }} />
            <div><b>{s.name}</b><div style={{ fontSize: 12, color: 'var(--text-2)' }}>{s.interval_minutes} хв · {s.last_run_at || 'ще не запускалось'}</div></div>
            <button style={{ marginLeft: 'auto' }} onClick={() => refresh(s.id)}>Оновити</button>
          </div>
        ))}
        {msg && <p>{msg}</p>}
      </div>
      <div className="glass" style={{ padding: 18, marginBottom: 14 }}>
        <h3>Журнал запусків</h3>
        {runs.map((r, i) => (
          <div key={i} style={{ display: 'flex', gap: 10, padding: '6px 0', fontSize: 14 }}>
            <span style={{ color: dot[r.status] || 'inherit' }}>●</span>
            <span>{r.status}</span>
            <span>+{r.added || 0} ~{r.updated || 0} −{r.removed || 0}</span>
            <span style={{ marginLeft: 'auto', color: 'var(--text-2)' }}>{r.started_at || r.when || ''}</span>
          </div>
        ))}
      </div>
      <div className="glass" style={{ padding: 18 }}>
        <h3>Каталог: {products.length} товарів</h3>
        {products.slice(0, 20).map((p) => (
          <div key={p.id || p.sku} style={{ display: 'flex', gap: 10, padding: '6px 0', fontSize: 14 }}>
            <b>{p.sku}</b><span>{p.name}</span>
            <span className="num" style={{ marginLeft: 'auto' }}>{Math.round(p.price)} ₴ · {p.stock} шт</span>
          </div>
        ))}
      </div>
    </div>
  );
}
