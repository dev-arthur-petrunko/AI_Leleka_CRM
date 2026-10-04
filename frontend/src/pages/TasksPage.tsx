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
  async function toggle(t: Task) {
    const next = t.status === 'open' ? 'done' : 'open';
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
  async function remove(t: Task) {
    try {
      await api(`/tasks/${t.id}`, { method: 'DELETE' });
      qc.invalidateQueries({ queryKey: ['tasks'] });
    } catch { /* ignore */ }
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
              return (
              <div key={task.id} style={{ display: 'flex', gap: 8, padding: '6px 0', alignItems: 'center' }}>
                <input type="checkbox" checked={task.status !== 'open'} onChange={() => toggle(task)}
                  aria-label={task.status === 'open' ? `Виконати: ${task.title}` : `Повернути: ${task.title}`}
                  style={{ width: 20, height: 20, accentColor: 'var(--primary)', flex: 'none', cursor: 'pointer' }} />
                <Badge tone={tone as 'bad'}>
                  <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
                    <Prio size={12} aria-hidden />{label}
                  </span>
                </Badge>
                <span style={{ textDecoration: task.status !== 'open' ? 'line-through' : 'none' }}>{task.title}</span>
                <span style={{ marginLeft: 'auto', color: 'var(--text-muted)', fontSize: 12 }}>
                  {task.due_at ? format(new Date(task.due_at), 'd MMM HH:mm', { locale: uk }) : ''}
                </span>
                <button onClick={() => remove(task)} aria-label={`Видалити: ${task.title}`}
                  style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)',
                    cursor: 'pointer', padding: 6, minHeight: 32 }}>×</button>
              </div>
              );
            })}
          </Card>
        );
      })}
      {data.length === 0 && <Card><EmptyState title="Завдань немає" hint="Створіть перше рядком вище." /></Card>}
    </div>
  );
}
