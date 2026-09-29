import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { api } from '../api';

type Deal = { id: string; title: string; amount: number; stage: string; client_id: string };
const STAGES = ['new', 'contacted', 'negotiation', 'won', 'lost'];
const MOCK: Deal[] = [
  { id: '1', title: 'Замовлення #412', amount: 45000, stage: 'negotiation', client_id: 'x' },
  { id: '2', title: 'Замовлення #371', amount: 8000, stage: 'new', client_id: 'x' },
];

export default function Deals() {
  const [deals, setDeals] = useState<Deal[]>(MOCK);
  useEffect(() => {
    api<{ items: Deal[] }>('/deals?limit=100').then((r) => {
      if (r) setDeals(r.items);
    });
  }, []);
  async function move(id: string, stage: string) {
    setDeals((ds) => ds.map((d) => (d.id === id ? { ...d, stage } : d))); // оптимістично
    await api(`/deals/${id}/stage?stage=${stage}`, { method: 'PATCH' });
  }
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5,minmax(180px,1fr))', gap: 12, overflowX: 'auto' }}>
      {STAGES.map((s) => (
        <div key={s} className="glass" style={{ padding: 10, minHeight: 200 }}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => move(e.dataTransfer.getData('text/plain'), s)}>
          <h4 style={{ textTransform: 'uppercase', fontSize: 12 }}>{s}</h4>
          {deals.filter((d) => d.stage === s).map((d) => (
            <div key={d.id} className="glass"
              draggable
              onDragStart={(e) => e.dataTransfer.setData('text/plain', d.id)}
              style={{ padding: 10, marginBottom: 8, cursor: 'grab', transition: 'transform .15s' }}
              onMouseDown={(e) => { (e.currentTarget as HTMLDivElement).style.transform = 'translateY(-3px)'; }}
              onMouseUp={(e) => { (e.currentTarget as HTMLDivElement).style.transform = ''; }}>
              <b>{d.title}</b>
              <div className="num">{Math.round(d.amount).toLocaleString('uk-UA')} ₴</div>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
