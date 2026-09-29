import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../api';

type Dash = {
  kpi: { new_leads_30d: number; conversion: number; avg_check: number };
  funnel: { stage: string; count: number }[];
  hot_leads: { deal_id: string; score: number; label: string; reasons: { stage: string } }[];
};

const MOCK: Dash = {
  kpi: { new_leads_30d: 27, conversion: 0.18, avg_check: 12400 },
  funnel: [
    { stage: 'new', count: 12 }, { stage: 'contacted', count: 8 },
    { stage: 'negotiation', count: 6 }, { stage: 'won', count: 5 }, { stage: 'lost', count: 3 },
  ],
  hot_leads: [{ deal_id: '412', score: 88, label: 'hot', reasons: { stage: 'negotiation' } }],
};

export default function Dashboard() {
  const [d, setD] = useState<Dash>(MOCK);
  const [live, setLive] = useState(false);
  useEffect(() => {
    api<Dash>('/analytics/dashboard').then((r) => {
      if (r) { setD(r); setLive(true); }
    });
  }, []);
  const kpis = [
    ['Нові ліди', d.kpi.new_leads_30d],
    ['Конверсія', `${Math.round(d.kpi.conversion * 100)}%`],
    ['Середній чек', `${Math.round(d.kpi.avg_check).toLocaleString('uk-UA')} ₴`],
    ['Джерело', live ? 'live API' : 'демо'],
  ];
  return (
    <div>
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
