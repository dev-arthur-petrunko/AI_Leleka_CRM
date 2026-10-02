import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, CheckSquare, Inbox, ShoppingCart } from 'lucide-react';
import { api } from '../api';
import { Card, EmptyState, ErrorState, Skeleton } from '../components/ui';
import { t } from '../i18n';

type Item = { kind: string; title: string; ref: { type: string; id: string } };
const KIND_ICON: Record<string, typeof Inbox> = {
  task_overdue: CheckSquare, deal_stuck: AlertTriangle, order_new: ShoppingCart, chat_unread: Inbox,
};
const KIND_LINK: Record<string, string> = {
  task_overdue: '/tasks', deal_stuck: '/deals', order_new: '/orders', chat_unread: '/inbox',
};

function greet(): string {
  const h = new Date().getHours();
  if (h < 12) return 'Доброго ранку';
  if (h < 18) return 'Добрий день';
  return 'Добрий вечір';
}

export default function Today() {
  const { data, error, isLoading, refetch } = useQuery({
    queryKey: ['today'],
    queryFn: () => api<{ items: Item[]; count: number }>('/today'),
  });
  if (isLoading) return <Card><Skeleton rows={5} /></Card>;
  if (error || !data) return <Card><ErrorState onRetry={() => refetch()} /></Card>;
  return (
    <div>
      <h2>{greet()} 👋</h2>
      <h3>Що зробити зараз ({data.count})</h3>
      {data.items.length === 0 && (
        <Card><EmptyState title="Все чисто" hint="Немає прострочених задач і завислих угод." /></Card>
      )}
      {data.items.map((it, i) => {
        const Icon = KIND_ICON[it.kind] || CheckSquare;
        return (
          <Card key={i} style={{ marginBottom: 8, padding: 12 }}>
            <Link to={KIND_LINK[it.kind] || '/'} style={{ display: 'flex', gap: 10, alignItems: 'center', color: 'var(--text)', textDecoration: 'none' }}>
              <Icon size={18} />{it.title}
            </Link>
          </Card>
        );
      })}
      <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
        {t('nav.clients')} і {t('nav.tasks')} — з {t('nav.today')} і пошуку Ctrl+K.
      </p>
    </div>
  );
}
