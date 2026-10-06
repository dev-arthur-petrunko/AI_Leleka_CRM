import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, ArrowRight, CheckCircle2, CheckSquare, Circle, Inbox, ShoppingCart, Sparkles } from 'lucide-react';
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
const KIND_TITLE: Record<string, string> = {
  task_overdue: 'Прострочені завдання',
  deal_stuck: 'Угоди без руху',
  order_new: 'Нові замовлення',
  chat_unread: 'Непрочитані повідомлення',
};
const KIND_TONE: Record<string, string> = {
  task_overdue: 'var(--danger)',
  deal_stuck: 'var(--warning)',
  order_new: 'var(--success)',
  chat_unread: 'var(--info)',
};

function greet(): string {
  const h = new Date().getHours();
  if (h < 12) return 'Доброго ранку';
  if (h < 18) return 'Добрий день';
  return 'Добрий вечір';
}

function Onboarding() {
  const integ = useQuery({ queryKey: ['ob-integ'], queryFn: () => api<any[]>('/integrations') });
  const orders = useQuery({
    queryKey: ['ob-orders'], queryFn: () => api<{ total: number }>('/orders?limit=1'),
  });
  const rules = useQuery({ queryKey: ['ob-rules'], queryFn: () => api<any[]>('/automations/rules') });
  const billing = useQuery({ queryKey: ['ob-billing'], queryFn: () => api<any>('/billing/current') });
  const loading = integ.isLoading || orders.isLoading || rules.isLoading || billing.isLoading;
  const steps = [
    { done: !loading && (integ.data || []).some((x: any) => x.has_key), label: 'Підключіть магазин', to: '/integrations' },
    { done: !loading && (orders.data?.total || 0) > 0, label: 'Отримайте перше замовлення', to: '/orders' },
    { done: !loading && (rules.data || []).length > 0, label: 'Увімкніть 5 правил', to: '/automations' },
    { done: !loading && (billing.data?.seats_used || 1) > 1, label: 'Запросіть команду', to: '/billing' },
  ];
  const done = steps.filter((s) => s.done).length;
  const total = steps.length;
  // 100% святкуємо один раз маленьким конфетті — і більше не повторюємо.
  // Хук ДО early-return: інакше кількість хуків плаває між рендерами (#310).
  useEffect(() => {
    if (loading || done !== total) return;
    let seen = false;
    try {
      seen = !!localStorage.getItem('leleka.onboarded');
    } catch { /* ignore */ }
    if (seen) return;
    try {
      localStorage.setItem('leleka.onboarded', '1');
    } catch { /* ignore */ }
    (async () => {
      try {
        const { loadAnim } = await import('../theme');
        if (loadAnim() !== 'all') return;
        const { default: confetti } = await import('canvas-confetti');
        confetti({ particleCount: 70, spread: 100, origin: { y: 0.3 },
          colors: ['#BD5A2A', '#2C5A5B', '#F7F2E9', '#D9A441'],
          disableForReducedMotion: true });
      } catch { /* ignore */ }
    })();
  }, [loading, done, total]);
  if (loading) return null;
  if (done === total) return null;
  return (
    <Card style={{ borderLeft: '4px solid var(--info)' }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
        <b>Старт за 5 хвилин</b>
        <span className="num" style={{ color: 'var(--text-muted)', fontSize: 12 }}>{done}/{steps.length}</span>
      </div>
      <div style={{ height: 8, borderRadius: 4, background: 'var(--bg-hover)', margin: '8px 0' }}>
        <div className="bar-grow" style={{ width: `${Math.round((done / steps.length) * 100)}%`, height: '100%',
          borderRadius: 4, background: 'linear-gradient(90deg,var(--info),var(--primary))' }} />
      </div>
      {steps.map((s) => (
        <Link key={s.label} to={s.to}
          style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '5px 0',
            color: s.done ? 'var(--text-muted)' : 'var(--text)', textDecoration: 'none', fontSize: 13 }}>
          {s.done
            ? <CheckCircle2 size={16} aria-hidden style={{ color: 'var(--success)' }} />
            : <Circle size={16} aria-hidden />}
          <span style={{ textDecoration: s.done ? 'line-through' : 'none' }}>{s.label}</span>
        </Link>
      ))}
    </Card>
  );
}

export default function Today() {
  const { data, error, isLoading, refetch } = useQuery({
    queryKey: ['today'],
    queryFn: () => api<{ items: Item[]; count: number }>('/today'),
  });
  if (isLoading) return <Card><Skeleton rows={5} /></Card>;
  if (error || !data) return <Card><ErrorState onRetry={() => refetch()} /></Card>;
  const groups: Record<string, Item[]> = {};
  for (const it of data.items) {
    (groups[it.kind] = groups[it.kind] || []).push(it);
  }
  const order = ['task_overdue', 'order_new', 'deal_stuck', 'chat_unread'].filter((k) => groups[k]);
  const rest = Object.keys(groups).filter((k) => !order.includes(k));
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <Onboarding />
      <Card style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <span aria-hidden
          style={{ width: 44, height: 44, borderRadius: '50%', flex: 'none',
            background: 'var(--primary)', color: 'var(--primary-fg)',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
          <Sparkles size={22} />
        </span>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 20, fontWeight: 800 }}>{greet()}</div>
          <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>
            {data.count === 0
              ? 'На сьогодні все чисто — можна зайнятись продажами.'
              : `До виконання: ${data.count} — почніть з простроченого.`}
          </div>
        </div>
      </Card>
      {data.items.length === 0 && (
        <Card><EmptyState title="Все чисто" hint="Немає прострочених задач і завислих угод."
          action={<Link to="/deals" style={{ color: 'var(--link)' }}>Перейти до угод</Link>} /></Card>
      )}
      {[...order, ...rest].map((kind) => {
        const Icon = KIND_ICON[kind] || CheckSquare;
        const tone = KIND_TONE[kind] || 'var(--info)';
        return (
          <section key={kind} aria-label={KIND_TITLE[kind] || kind} className="data-in">
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, margin: '4px 2px 8px' }}>
              <h3 style={{ margin: 0, fontSize: 15 }}>{KIND_TITLE[kind] || kind}</h3>
              <span className="num" style={{ color: 'var(--text-muted)', fontSize: 13 }}>{groups[kind].length}</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(280px,1fr))', gap: 8 }}>
              {groups[kind].map((it, i) => (
                <Card key={`${kind}-${i}`} style={{ padding: 12 }}>
                  <Link to={KIND_LINK[it.kind] || '/'}
                    style={{ display: 'flex', gap: 10, alignItems: 'center', color: 'var(--text)', textDecoration: 'none', minHeight: 40 }}>
                    <span aria-hidden
                      style={{ width: 36, height: 36, borderRadius: 10, flex: 'none',
                        background: `${tone}22`, color: tone,
                        display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
                      <Icon size={18} />
                    </span>
                    <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis' }}>{it.title}</span>
                    <ArrowRight size={16} aria-hidden style={{ color: 'var(--text-muted)', flex: 'none' }} />
                  </Link>
                </Card>
              ))}
            </div>
          </section>
        );
      })}
      <p style={{ color: 'var(--text-muted)', fontSize: 13, margin: 0 }}>
        {t('nav.clients')} і {t('nav.tasks')} — з {t('nav.today')} і пошуку Ctrl+K.
      </p>
    </div>
  );
}
