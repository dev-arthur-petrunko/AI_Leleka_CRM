import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { format } from 'date-fns';
import { uk } from 'date-fns/locale';
import { api } from '../api';
import { Button, Card, EmptyState, ErrorState, Skeleton } from '../components/ui';

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
    await api('/tasks', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: quick }) });
    setQuick('');
    qc.invalidateQueries({ queryKey: ['tasks'] });
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
            {list.map((t) => (
              <div key={t.id} style={{ display: 'flex', gap: 8, padding: '6px 0', alignItems: 'center' }}>
                <span>{t.priority === 'high' ? '🔴' : t.priority === 'low' ? '⚪' : '🟡'}</span>
                <span style={{ textDecoration: t.status !== 'open' ? 'line-through' : 'none' }}>{t.title}</span>
                <span style={{ marginLeft: 'auto', color: 'var(--text-muted)', fontSize: 12 }}>
                  {t.due_at ? format(new Date(t.due_at), 'd MMM HH:mm', { locale: uk }) : ''}
                </span>
              </div>
            ))}
          </Card>
        );
      })}
      {data.length === 0 && <Card><EmptyState title="Завдань немає" hint="Створіть перше рядком вище." /></Card>}
    </div>
  );
}
