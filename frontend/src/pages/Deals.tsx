import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import { Badge, Button, Card, EmptyState, ErrorState, Skeleton } from '../components/ui';
import { t } from '../i18n';

type Deal = { id: string; title: string; amount: number; stage: string; client_id: string };
const STAGES = ['new', 'contacted', 'negotiation', 'won', 'lost'];
const stageTone = (s: string): 'info' | 'ok' | 'warn' | 'bad' =>
  s === 'won' ? 'ok' : s === 'lost' ? 'bad' : s === 'negotiation' ? 'warn' : 'info';

export default function Deals() {
  const [view, setView] = useState<'kanban' | 'table'>('kanban');
  const [stageFilter, setStageFilter] = useState('');
  const qc = useQueryClient();
  const { data, error, isLoading, refetch } = useQuery({
    queryKey: ['deals', stageFilter],
    queryFn: () => api<{ total: number; items: Deal[] }>(
      `/deals?limit=100${stageFilter ? `&stage=${stageFilter}` : ''}`),
  });
  async function move(id: string, stage: string, loss_reason?: string) {
    const prev = qc.getQueryData(['deals', stageFilter]);
    qc.setQueryData(['deals', stageFilter], (old: any) => ({
      ...old, items: old.items.map((d: Deal) => (d.id === id ? { ...d, stage } : d)),
    }));
    const r = await api(`/deals/${id}/stage?stage=${stage}${loss_reason ? `&loss_reason=${encodeURIComponent(loss_reason)}` : ''}`, { method: 'PATCH' });
    if (!r) qc.setQueryData(['deals', stageFilter], prev); // відкат при помилці
    else qc.invalidateQueries({ queryKey: ['deals'] });
  }
  async function convert(id: string) {
    const r = await api(`/deals/${id}/convert-to-order`, { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
    alert(r ? `Замовлення: ${(r as any).order_id}` : 'Не вдалося');
    refetch();
  }
  if (isLoading) return <Card><Skeleton rows={6} /></Card>;
  if (error || !data) return <Card><ErrorState onRetry={() => refetch()} /></Card>;
  const deals = data.items;
  return (
    <div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <Button variant={view === 'kanban' ? 'primary' : 'ghost'} onClick={() => setView('kanban')}>Канбан</Button>
        <Button variant={view === 'table' ? 'primary' : 'ghost'} onClick={() => setView('table')}>Таблиця</Button>
        <select value={stageFilter} onChange={(e) => setStageFilter(e.target.value)} aria-label="Стадія">
          <option value="">всі стадії</option>
          {STAGES.map((s) => <option key={s} value={s}>{t('stage.' + s)}</option>)}
        </select>
      </div>
      {deals.length === 0 && (
        <Card><EmptyState title="Угод немає" hint="Створіть першу угоду." /></Card>
      )}
      {view === 'kanban' ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5,minmax(180px,1fr))', gap: 12, overflowX: 'auto' }}>
          {STAGES.map((s) => {
            const col = deals.filter((d) => d.stage === s);
            const sum = col.reduce((a, d) => a + d.amount, 0);
            return (
              <div key={s} className="glass" style={{ padding: 10, minHeight: 200 }}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  const id = e.dataTransfer.getData('text/plain');
                  if (s === 'lost') {
                    const reason = prompt('Причина (обовʼязково):', 'ціна');
                    if (!reason) return;
                    move(id, s, reason);
                  } else move(id, s);
                }}>
                <h4>{t('stage.' + s)} · {col.length} · <span className="num">{Math.round(sum).toLocaleString('uk-UA')} ₴</span></h4>
                {col.map((d) => (
                  <div key={d.id} className="glass" draggable
                    onDragStart={(e) => e.dataTransfer.setData('text/plain', d.id)}
                    style={{ padding: 10, marginBottom: 8, cursor: 'grab' }}>
                    <b>Угода #{d.title.replace(/^Замовлення\s*/, '')}</b>
                    <div className="num">{Math.round(d.amount).toLocaleString('uk-UA')} ₴</div>
                    <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                      <Badge tone={stageTone(d.stage)}>{t('stage.' + d.stage)}</Badge>
                      {s !== 'won' && <button onClick={() => convert(d.id)}>→ замовлення</button>}
                    </div>
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      ) : (
        <Card>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
            <thead><tr><th>Назва</th><th>Стадія</th><th>Сума</th></tr></thead>
            <tbody>
              {deals.map((d) => (
                <tr key={d.id} style={{ borderTop: '1px solid var(--border)' }}>
                  <td>{d.title}</td>
                  <td><Badge tone={stageTone(d.stage)}>{t('stage.' + d.stage)}</Badge></td>
                  <td className="num">{Math.round(d.amount).toLocaleString('uk-UA')} ₴</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
