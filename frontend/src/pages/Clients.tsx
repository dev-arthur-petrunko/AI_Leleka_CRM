import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import { Badge, Card, EmptyState, ErrorState, Skeleton } from '../components/ui';
import { t } from '../i18n';

type Client = { id: string; name: string; phone?: string; segment: string };

function fmtPhone(p?: string): string {
  if (!p) return '';
  const d = p.replace(/\D/g, '');
  const m = d.match(/^380(\d{2})(\d{3})(\d{2})(\d{2})$/);
  return m ? `+380 ${m[1]} ${m[2]} ${m[3]} ${m[4]}` : p;
}

export default function Clients() {
  const [q, setQ] = useState('');
  const [seg, setSeg] = useState('');
  const { data, error, isLoading, refetch } = useQuery({
    queryKey: ['clients', q, seg],
    queryFn: () => api<{ total: number; items: Client[] }>(
      `/clients?limit=50${q ? `&q=${encodeURIComponent(q)}` : ''}${seg ? `&segment=${seg}` : ''}`),
  });
  if (isLoading) return <Card><Skeleton rows={6} /></Card>;
  if (error || !data) return <Card><ErrorState onRetry={() => refetch()} /></Card>;
  return (
    <Card>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Пошук…" aria-label="Пошук клієнтів"
          style={{ flex: 1, padding: 10, borderRadius: 8 }} />
        <select value={seg} onChange={(e) => setSeg(e.target.value)} aria-label="Сегмент">
          <option value="">всі</option>
          {['new', 'regular', 'vip', 'lost'].map((s) => <option key={s} value={s}>{t('segment.' + s)}</option>)}
        </select>
      </div>
      {data.items.length === 0 && (
        <EmptyState title="Клієнтів не знайдено" hint="Змініть пошук або додайте першого клієнта." />
      )}
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
        <thead><tr><th>Імʼя</th><th>Телефон</th><th>Сегмент</th></tr></thead>
        <tbody>
          {data.items.map((c) => (
            <tr key={c.id} style={{ borderTop: '1px solid var(--border)' }}>
              <td>{c.name}</td>
              <td className="num">{fmtPhone(c.phone)}</td>
              <td><Badge>{t('segment.' + c.segment)}</Badge></td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
