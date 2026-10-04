import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, MinusCircle, RefreshCw, XCircle } from 'lucide-react';
import { api } from '../api';
import { Badge, Button, Card, EmptyState, ErrorState, Skeleton } from '../components/ui';
import { t } from '../i18n';

type Src = { id: string; name: string; last_status?: string; last_run_at?: string; interval_minutes: number };
type Run = { source_id?: string; source?: string; status: string; added?: number; updated?: number; removed?: number; started_at?: string; when?: string };

function statusTone(s?: string): 'info' | 'ok' | 'warn' | 'bad' {
  if (s === 'ok') return 'ok';
  if (s === 'error') return 'bad';
  if (s === 'skipped') return 'warn';
  return 'info';
}

function StatusIcon({ s }: { s?: string }) {
  if (s === 'ok') return <CheckCircle2 size={16} aria-hidden style={{ color: 'var(--success)' }} />;
  if (s === 'error') return <XCircle size={16} aria-hidden style={{ color: 'var(--danger)' }} />;
  if (s === 'skipped') return <MinusCircle size={16} aria-hidden style={{ color: 'var(--warning)' }} />;
  return <MinusCircle size={16} aria-hidden style={{ color: 'var(--text-muted)' }} />;
}

function statusLabel(s?: string): string {
  if (s === 'ok') return t('feed.ok');
  if (s === 'error') return t('feed.error');
  if (s === 'skipped') return t('feed.skipped');
  return t('feed.never');
}

export default function FeedHub() {
  const qc = useQueryClient();
  const [msg, setMsg] = useState('');
  const sources = useQuery({ queryKey: ['feeds'], queryFn: () => api<Src[]>('/feedhub/sources') });
  const runs = useQuery({ queryKey: ['feed-runs'], queryFn: () => api<Run[]>('/feedhub/runs?limit=10') });
  const products = useQuery({
    queryKey: ['feed-products'],
    queryFn: () => api<{ items: any[] }>('/feedhub/products?limit=50'),
  });
  async function refresh(id: string) {
    setMsg('Оновлення…');
    try {
      const r = await api<{ ok: boolean; added: number; updated: number; removed: number; status: string; error?: string }>(
        `/feedhub/sources/${id}/run`, { method: 'POST' });
      if (r && r.ok) {
        setMsg(`Готово (${r.status || 'ok'}): +${r.added || 0} ~${r.updated || 0} −${r.removed || 0}`);
      } else {
        setMsg(`Не вдалося: ${r?.error || 'помилка фіда'}. Деталі — у сповіщеннях.`);
      }
      qc.invalidateQueries({ queryKey: ['feeds'] });
      qc.invalidateQueries({ queryKey: ['feed-runs'] });
      qc.invalidateQueries({ queryKey: ['feed-products'] });
    } catch {
      setMsg('Не вдалося оновити. Спробуйте ще раз.');
    }
  }
  if (sources.isLoading || runs.isLoading || products.isLoading) return <Card><Skeleton rows={6} /></Card>;
  if (sources.error || runs.error || products.error
    || !sources.data || !runs.data || !products.data) {
    return <Card><ErrorState onRetry={() => {
      sources.refetch(); runs.refetch(); products.refetch();
    }} /></Card>;
  }
  const items = products.data.items || [];
  return (
    <div>
      <Card style={{ marginBottom: 14 }}>
        <h3>Джерела фідів</h3>
        {sources.data.length === 0 && (
          <EmptyState title="Джерел поки немає"
            hint="Додайте перше джерело через API (POST /feedhub/sources)." />
        )}
        {sources.data.map((s) => (
          <div key={s.id} style={{ display: 'flex', gap: 10, alignItems: 'center', padding: '10px 0' }}>
            <StatusIcon s={s.last_status} />
            <div>
              <b>{s.name}</b>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                {s.interval_minutes} хв · {s.last_run_at || t('feed.never')}
              </div>
            </div>
            <span style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
              <Badge tone={statusTone(s.last_status)}>{statusLabel(s.last_status)}</Badge>
              <Button variant="ghost" onClick={() => refresh(s.id)}>
                <RefreshCw size={14} /> Оновити
              </Button>
            </span>
          </div>
        ))}
        {msg && <p>{msg}</p>}
      </Card>
      <Card style={{ marginBottom: 14 }}>
        <h3>Журнал запусків</h3>
        {runs.data.length === 0 && <EmptyState title="Запусків ще не було" />}
        {runs.data.map((r, i) => (
          <div key={i} style={{ display: 'flex', gap: 10, padding: '6px 0', fontSize: 14, alignItems: 'center' }}>
            <StatusIcon s={r.status} />
            <Badge tone={statusTone(r.status)}>{statusLabel(r.status)}</Badge>
            <span className="num">+{r.added || 0} ~{r.updated || 0} −{r.removed || 0}</span>
            <span style={{ marginLeft: 'auto', color: 'var(--text-muted)' }}>{r.started_at || r.when || ''}</span>
          </div>
        ))}
      </Card>
      <Card>
        <h3>Каталог: {items.length} товарів</h3>
        {items.length === 0 && <EmptyState title="Каталог порожній" hint="Запустіть оновлення джерела." />}
        {items.slice(0, 20).map((p) => (
          <div key={p.id || p.sku} style={{ display: 'flex', gap: 10, padding: '6px 0', fontSize: 14 }}>
            <b>{p.sku}</b><span>{p.name}</span>
            <span className="num" style={{ marginLeft: 'auto' }}>{Math.round(p.price)} ₴ · {p.stock} шт</span>
          </div>
        ))}
      </Card>
    </div>
  );
}
