import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../api';

type Dash = {
  kpi: { new_leads_30d: number; conversion: number; avg_check: number };
  funnel: { stage: string; count: number }[];
  hot_leads: { deal_id: string; score: number; label: string; reasons: { stage: string } }[];
};

function Skeleton() {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', gap: 14 }}>
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="glass" style={{ padding: 18, opacity: 0.6 }}>
          <div style={{ height: 28, background: 'var(--text-2)', borderRadius: 8, opacity: 0.3 }} />
          <div style={{ height: 12, marginTop: 8, background: 'var(--text-2)', borderRadius: 6, opacity: 0.2 }} />
        </div>
      ))}
    </div>
  );
}

function Body() {
  const { data, error, isLoading, refetch } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api<Dash>('/analytics/dashboard'),
  });
  const [demo, setDemo] = useState(false);
  useEffect(() => {
    if (new URLSearchParams(location.search).get('demo') === '1') setDemo(true);
  }, []);
  if (isLoading) return <Skeleton />;
  if (error || (!data && !demo)) {
    return (
      <div className="glass" style={{ padding: 28, textAlign: 'center' }}>
        <h3>Немає звʼязку з сервером</h3>
        <p style={{ color: 'var(--text-2)' }}>Перевірте API і токен, або відкрийте демо.</p>
        <button onClick={() => refetch()}>Повторити</button>{' '}
        <button onClick={() => setDemo(true)}>Демо</button>
      </div>
    );
  }
  const d: Dash = data || {
    kpi: { new_leads_30d: 27, conversion: 0.18, avg_check: 12400 },
    funnel: [
      { stage: 'new', count: 12 }, { stage: 'contacted', count: 8 },
      { stage: 'negotiation', count: 6 }, { stage: 'won', count: 5 }, { stage: 'lost', count: 3 },
    ],
    hot_leads: [{ deal_id: '412', score: 88, label: 'hot', reasons: { stage: 'negotiation' } }],
  };
  const kpis = [
    ['Нові ліди', d.kpi.new_leads_30d],
    ['Конверсія', `${Math.round(d.kpi.conversion * 100)}%`],
    ['Середній чек', `${Math.round(d.kpi.avg_check).toLocaleString('uk-UA')} ₴`],
    ['Джерело', demo && !data ? 'демо' : 'live API'],
  ];
  return (
    <div>
      {(demo && !data) && <p style={{ color: 'var(--warn)' }}>🧪 Демо: показано не ваші дані</p>}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', gap: 14, marginBottom: 14 }}>
        {kpis.map(([l, v], i) => (
          <motion.div key={l} className="glass" style={{ padding: 18 }}
            initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.07 }}>
            <div className="num" style={{ fontSize: 28, fontWeight: 800 }}>{v}</div>
            <div style={{ color: 'var(--text-2)', fontSize: 13 }}>{l}</div>
          </motion.div>
        ))}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 14 }}>
        <div className="glass" style={{ padding: 18 }}>
          <h3>Воронка</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={d.funnel} layout="vertical">
              <XAxis type="number" hide />
              <YAxis dataKey="stage" type="category" width={100} tick={{ fill: 'var(--text-2)', fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="count" fill="url(#g)" radius={[0, 8, 8, 0]} />
              <defs>
                <linearGradient id="g" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0" stopColor="#38bdf8" />
                  <stop offset="1" stopColor="#8b5cf6" />
                </linearGradient>
              </defs>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="glass" style={{ padding: 18 }}>
          <h3>🔥 Гарячі угоди</h3>
          {d.hot_leads.length === 0 && <p style={{ color: 'var(--text-2)' }}>Порожньо — підключіть Prom, щоб зʼявились угоди.</p>}
          {d.hot_leads.slice(0, 6).map((h) => (
            <div key={h.deal_id} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0' }}>
              <span>#{h.deal_id} · {h.reasons.stage}</span>
              <b style={{ color: h.score >= 70 ? 'var(--ok)' : 'var(--warn)' }}>{h.score}</b>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  return <Body />;
}
