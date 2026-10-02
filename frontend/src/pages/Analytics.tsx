import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Bar, BarChart, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../api';
import { Card, EmptyState, ErrorState, Skeleton, Tabs } from '../components/ui';

const PERIODS = ['7', '30', '90'];

export default function Analytics() {
  const [days, setDays] = useState('30');
  const rev = useQuery({
    queryKey: ['rev', days], queryFn: () => api<{ by_day: any[]; aov: number }>(`/analytics/shop/revenue?days=${days}`),
  });
  const dash = useQuery({
    queryKey: ['dash'], queryFn: () => api<any>('/analytics/dashboard'),
  });
  if (rev.isLoading || dash.isLoading) return <Card><Skeleton rows={6} /></Card>;
  if (rev.error || dash.error || !rev.data || !dash.data) {
    return <Card><ErrorState onRetry={() => { rev.refetch(); dash.refetch(); }} /></Card>;
  }
  const grid = getComputedStyle(document.documentElement).getPropertyValue('--chart-grid') || '#888';
  return (
    <div>
      <Tabs tabs={PERIODS.map((p) => `${p} днів`)} value={`${days} днів`}
        onChange={(v) => setDays(v.split(' ')[0])} />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        <Card>
          <h3>Виручка по днях (вісь з нуля)</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={rev.data.by_day}>
              <XAxis dataKey="day" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} domain={[0, 'auto']} allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="total" fill="var(--info)" radius={[6, 6, 0, 0]} label={{ position: 'top', fontSize: 10 }} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card>
          <h3>Воронка (звужується, % переходу)</h3>
          <FunnelChart data={dash.data.funnel} />
        </Card>
      </div>
      <Card style={{ marginTop: 14 }}>
        <h3>Прогноз (пунктир)</h3>
        <ForecastChart history={(dash.data.forecast?.history || []).map((h: any) => ({ m: h.month, v: h.total }))} />
      </Card>
      {rev.data.by_day.length === 0 && (
        <Card><EmptyState title="Поки порожньо" hint="Дані зʼявляться після перших замовлень." /></Card>
      )}
    </div>
  );
}

function FunnelChart({ data }: { data: { stage: string; count: number }[] }) {
  const total = data[0]?.count || 1;
  return (
    <div>
      {data.map((f, i) => {
        const prev = i === 0 ? null : Math.round((f.count / (data[i - 1].count || 1)) * 100);
        return (
          <div key={f.stage} style={{ marginBottom: 6 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
              <span>{f.stage}</span><b className="num">{f.count}</b>
            </div>
            <div style={{ height: 14, borderRadius: 7, background: 'var(--bg-hover)' }}>
              <div style={{ width: `${Math.round((f.count / total) * 100)}%`, height: '100%',
                borderRadius: 7, background: 'linear-gradient(90deg,var(--info),var(--primary))' }} />
            </div>
            {prev !== null && <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>→ {prev}% з попередньої</div>}
          </div>
        );
      })}
    </div>
  );
}

function ForecastChart({ history }: { history: { m: string; v: number }[] }) {
  const data = [...history, { m: 'прогноз', v: history.length ? history[history.length - 1].v : 0, dash: true }];
  return (
    <ResponsiveContainer width="100%" height={180}>
      <LineChart data={data}>
        <XAxis dataKey="m" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} domain={[0, 'auto']} />
        <Tooltip />
        <Line type="monotone" dataKey="v" stroke="var(--success)" strokeDasharray="6 4" dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
