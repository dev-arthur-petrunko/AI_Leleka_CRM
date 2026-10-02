import { useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, PlugZap, RefreshCw, XCircle } from 'lucide-react';
import { api } from '../api';
import { Button, Card, EmptyState, ErrorState, Skeleton } from '../components/ui';

type Integ = { provider: string; is_active: boolean; has_key: boolean; status: string;
  last_error?: string; last_sync_at?: string };

export default function IntegrationsPage() {
  const qc = useQueryClient();
  const { data, error, isLoading, refetch } = useQuery({
    queryKey: ['integrations'], queryFn: () => api<Integ[]>('/integrations'),
  });
  async function syncNow(provider: string) {
    await api(`/integrations/${provider}/import-orders`, { method: 'POST' });
    qc.invalidateQueries({ queryKey: ['integrations'] });
  }
  if (isLoading) return <Card><Skeleton rows={5} /></Card>;
  if (error || !data) return <Card><ErrorState onRetry={() => refetch()} /></Card>;
  return (
    <Card>
      <h2>Інтеграції</h2>
      {data.length === 0 && (
        <EmptyState title="Нічого не підключено" hint="Почніть з Prom або Rozetka — замовлення потечуть самі." />
      )}
      {data.map((r) => (
        <div key={r.provider} style={{ display: 'flex', gap: 10, alignItems: 'center',
          padding: '12px 0', borderTop: '1px solid var(--border)' }}>
          {r.status === 'ok' && r.has_key
            ? <CheckCircle2 size={20} color="var(--success)" aria-label="Підключено" />
            : <XCircle size={20} color="var(--danger)" aria-label="Помилка" />}
          <div>
            <b>{r.provider}</b>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {r.status === 'ok' && r.has_key ? 'Підключено' : r.status === 'auth_failed' ? 'Помилка: токен недійсний' : 'Не підключено'}
              {r.last_sync_at ? ` · синхронізовано ${r.last_sync_at}` : ''}
              {r.last_error ? ` · ${r.last_error}` : ''}
            </div>
          </div>
          <span style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
            <Button variant="ghost" onClick={() => syncNow(r.provider)}>
              <RefreshCw size={14} /> Синхронізувати
            </Button>
            <Button variant="ghost"><PlugZap size={14} /> Тест</Button>
          </span>
        </div>
      ))}
    </Card>
  );
}
