import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { format } from 'date-fns';
import { uk } from 'date-fns/locale';
import { ArrowDown, ArrowUp, Minus } from 'lucide-react';
import { api } from '../api';
import { Badge, Button, Card, EmptyState, ErrorState, Skeleton } from '../components/ui';
import { t } from '../i18n';

type Task = { id: string; title: string; status: string; priority: string; due_at?: string };

function group(t: Task): string {
  if (t.status !== 'open') return 'done';
  if (!t.due_at) return 'later';
  const d = new Date(t.due_at).toDateString();
  const today = new Date().toDateString();
  const tomorrow = new Date(Date.now() + 864e5).toDateString();
  if (d < today) return 'overdue';
  if (d === today) return 'today';
  if (d === tomorrow) return 'tomorrow';
  return 'later';
}
const GROUPS: [string, string][] = [
  ['overdue', 'Прострочені'], ['today', 'Сьогодні'], ['tomorrow', 'Завтра'],
  ['later', 'Пізніше'], ['done', 'Виконані'],
];

export default function TasksPage() {
  const [quick, setQuick] = useState('');
  const qc = useQueryClient();
  const { data, error, isLoading, refetch } = useQuery({
    queryKey: ['tasks'], queryFn: () => api<Task[]>('/tasks?limit=200'),
  });
  async function add() {
    if (!quick.trim()) return;
    try {
      await api('/tasks', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: quick }) });
      setQuick('');
      qc.invalidateQueries({ queryKey: ['tasks'] });
    } catch { /* помилка створення — список лишається, видно при наступному refetch */ }
  }
  const [leavingId, setLeavingId] = useState<string | null>(null);
  // дія з анімацією виходу: рядок складається 200мс, потім виклик
  async function act(t: Task, kind: 'toggle' | 'reopen' | 'remove') {
    if (leavingId) return;
    setLeavingId(t.id);
    await new Promise((r) => setTimeout(r, 200));
    setLeavingId(null);
    if (kind === 'remove') {
      try {
        await api(`/tasks/${t.id}`, { method: 'DELETE' });
        qc.invalidateQueries({ queryKey: ['tasks'] });
      } catch { /* ignore */ }
      return;
    }
    const next = kind === 'reopen' ? 'open' : 'done';
    qc.setQueryData<Task[]>(['tasks'], (old) =>
      (old || []).map((x) => (x.id === t.id ? { ...x, status: next } : x)));
    try {
      await api(`/tasks/${t.id}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: next }),
      });
    } catch {
      qc.invalidateQueries({ queryKey: ['tasks'] });
    }
  }
  if (isLoading) return <Card><Skeleton rows={6} /></Card>;
  if (error || !data) return <Card><ErrorState onRetry={() => refetch()} /></Card>;
  return (
    <div>
      <Card style={{ marginBottom: 12 }}>
        <div style={{ display: 'flex', gap: 8 }}>
          <input value={quick} onChange={(e) => setQuick(e.target.value)} placeholder="Швидке завдання… (Enter)"
            onKeyDown={(e) => e.key === 'Enter' && add()} aria-label="Нове завдання"
            style={{ flex: 1, padding: 10, borderRadius: 8 }} />
          <Button onClick={add}>Додати</Button>
        </div>
      </Card>
      {GROUPS.map(([key, label]) => {
        const list = data.filter((t) => group(t) === key);
        if (!list.length) return null;
        return (
          <Card key={key} style={{ marginBottom: 12 }}>
            <h3>{label} ({list.length})</h3>
            {list.map((task) => {
              const Prio = task.priority === 'high' ? ArrowUp : task.priority === 'low' ? ArrowDown : Minus;
              const tone = task.priority === 'high' ? 'bad' : task.priority === 'low' ? 'info' : 'warn';
              const label = t('prio.' + (task.priority === 'high' ? 'high' : task.priority === 'low' ? 'low' : 'normal'));
              const done = task.status !== 'open';
              const leaving = leavingId === task.id;
              return (
              <div key={task.id} className={leaving ? 'task-leave' : 'card-in'}
                style={{ display: 'flex', gap: 8, padding: '6px 0', alignItems: 'center',
                  overflow: 'hidden' }}>
                <button onClick={() => act(task, done ? 'reopen' : 'toggle')}
                  aria-label={done ? `Повернути: ${task.title}` : `Виконати: ${task.title}`}
                  aria-pressed={done}
                  style={{ background: 'transparent', border: 'none', padding: 4,
                    cursor: 'pointer', flex: 'none' }}>
                  <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden>
                    <rect x="2" y="2" width="18" height="18" rx="6"
                      fill={done ? 'var(--success)' : 'transparent'}
                      stroke={done ? 'var(--success)' : 'var(--border)'}
                      strokeWidth="2" className="box-pop" />
                    {done && (
                      <path d="M6.5 11.5 l3.5 3.5 l6 -8" fill="none"
                        stroke="var(--primary-fg)" strokeWidth="2.4"
                        strokeLinecap="round" strokeLinejoin="round"
                        className="check-draw" />
                    )}
                  </svg>
                </button>
                <Badge tone={tone as 'bad'}>
                  <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
                    <Prio size={12} aria-hidden />{label}
                  </span>
                </Badge>
                <span style={{ textDecoration: task.status !== 'open' ? 'line-through' : 'none' }}>{task.title}</span>
                <span style={{ marginLeft: 'auto', color: 'var(--text-muted)', fontSize: 12 }}>
                  {task.due_at ? format(new Date(task.due_at), 'd MMM HH:mm', { locale: uk }) : ''}
                </span>
                <button onClick={() => act(task, 'remove')} aria-label={`Видалити: ${task.title}`}
                  style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)',
                    cursor: 'pointer', padding: 6, minHeight: 32 }}>×</button>
              </div>
              );
            })}
          </Card>
        );
      })}
      {data.length === 0 && <Card><EmptyState title="Завдань немає" hint="Створіть перше рядком вище." /></Card>}
      {data.length > 0 && !data.some((t) => t.status === 'open') && (
        <Card><EmptyState title="Усе зроблено" hint="Немає відкритих завдань. Так тримати!" /></Card>
      )}
    </div>
  );
}
