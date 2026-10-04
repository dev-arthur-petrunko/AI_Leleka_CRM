import { useQuery } from '@tanstack/react-query';
import { BellRing } from 'lucide-react';
import { api } from '../api';
import { Card, EmptyState, ErrorState, Skeleton } from '../components/ui';

type Note = { text: string; kind?: string; ref?: unknown; ts?: number };

function clean(s: string): string {
  // тексти з сервера іноді починаються з емодзі — в інтерфейсі їх не показуємо
  return (s || '').replace(/^[\u2600-\u27BF\u2B00-\u2BFF\uFE0F ]+/, '');
}

function fmtTs(ts?: number): string {
  if (!ts) return '';
  try {
    return new Date(ts * 1000).toLocaleString('uk-UA');
  } catch {
    return '';
  }
}

export default function NotificationsPage() {
  const { data, error, isLoading, refetch } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => api<Note[]>('/notifications'),
    refetchInterval: 30000,
  });
  if (isLoading) return <Card><Skeleton rows={5} /></Card>;
  if (error || !data) return <Card><ErrorState onRetry={() => refetch()} /></Card>;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 720 }}>
      {data.length === 0 && (
        <Card><EmptyState title="Сповіщень немає" hint="Помилки синхронізації і важливі події зʼявляться тут." /></Card>
      )}
      {data.map((n, i) => (
        <Card key={i} style={{ padding: 12, display: 'flex', gap: 10, alignItems: 'flex-start' }}>
          <BellRing size={18} aria-hidden style={{ color: 'var(--warning)', flex: 'none', marginTop: 2 }} />
          <div style={{ minWidth: 0 }}>
            <div>{clean(n.text)}</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {[n.kind, fmtTs(n.ts)].filter(Boolean).join(' · ')}
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}
