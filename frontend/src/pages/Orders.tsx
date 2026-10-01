import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api';

type Order = { id: string; order_number?: string; external_id: string; source: string;
  status: string; payment_status: string; total: number; currency: string };

export default function Orders() {
  const [status, setStatus] = useState('');
  const [source, setSource] = useState('');
  const [page, setPage] = useState(0);
  const limit = 20;
  const { data, error, isLoading, refetch } = useQuery({
    queryKey: ['orders', status, source, page],
    queryFn: () => api<{ total: number; items: Order[] }>(
      `/orders?limit=${limit}&offset=${page * limit}` +
      (status ? `&status=${status}` : '') + (source ? `&source=${source}` : '')),
  });
  if (isLoading) return <div className="glass" style={{ padding: 20 }}>Завантаження…</div>;
  if (error || !data) {
    return (
      <div className="glass" style={{ padding: 28, textAlign: 'center' }}>
        <h3>Немає звʼязку з сервером</h3>
        <button onClick={() => refetch()}>Повторити</button>
      </div>
    );
  }
  return (
    <div className="glass" style={{ padding: 18 }}>
      <h3>Замовлення · {data.total}</h3>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(0); }}>
          <option value="">всі статуси</option>
          {['new', 'confirmed', 'packed', 'shipped', 'delivered', 'cancelled', 'returned'].map((s) => (
            <option key={s} value={s}>{s}</option>))}
        </select>
        <select value={source} onChange={(e) => { setSource(e.target.value); setPage(0); }}>
          <option value="">всі джерела</option>
          {['prom', 'rozetka', 'site', 'manual'].map((s) => (
            <option key={s} value={s}>{s}</option>))}
        </select>
      </div>
      {data.items.length === 0 && <p>Порожньо. <a href="/feedhub">Підключіть Prom</a>, щоб зʼявились замовлення.</p>}
      {data.items.map((o) => (
        <div key={o.id} style={{ display: 'flex', gap: 10, padding: '8px 0', borderTop: '1px solid var(--glass-border)', fontSize: 14 }}>
          <b>{o.order_number || o.external_id}</b>
          <span>{o.source}</span>
          <span>● {o.status}</span>
          <span className="num" style={{ marginLeft: 'auto' }}>{Math.round(o.total)} {o.currency}</span>
        </div>
      ))}
      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        <button disabled={page === 0} onClick={() => setPage((p) => p - 1)}>←</button>
        <button disabled={(page + 1) * limit >= data.total} onClick={() => setPage((p) => p + 1)}>→</button>
      </div>
    </div>
  );
}
