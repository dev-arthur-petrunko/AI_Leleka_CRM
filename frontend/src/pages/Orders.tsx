import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Banknote, ChevronLeft, ChevronRight, Package, Store, Truck } from 'lucide-react';
import { api } from '../api';
import { Badge, Button, Card, EmptyState, ErrorState, Input, Select, Skeleton } from '../components/ui';
import OrderDrawer from '../components/OrderDrawer';
import { t } from '../i18n';

type Order = { id: string; order_number?: string; external_id: string; source: string;
  status: string; payment_status: string; total: number; currency: string };

function statusTone(s: string): 'info' | 'ok' | 'warn' | 'bad' {
  if (s === 'delivered') return 'ok';
  if (s === 'cancelled' || s === 'returned') return 'bad';
  if (s === 'new') return 'warn';
  return 'info';
}

function payTone(s: string): 'info' | 'ok' | 'warn' | 'bad' {
  if (s === 'paid') return 'ok';
  if (s === 'partial') return 'warn';
  if (s === 'refunded') return 'bad';
  return 'info';
}

export default function Orders() {
  const [status, setStatus] = useState('');
  const [source, setSource] = useState('');
  const [pay, setPay] = useState('');
  const [q, setQ] = useState('');
  const [page, setPage] = useState(0);
  const limit = 20;
  const [openId, setOpenId] = useState<string | null>(null);
  const [params] = useSearchParams();
  useEffect(() => {
    const oid = params.get('order');
    if (oid) setOpenId(oid);
  }, [params]);
  const [flash, setFlash] = useState<Set<string>>(new Set());
  const known = useRef<Set<string>>(new Set());
  const [fresh, setFresh] = useState(0);
  const { data, error, isLoading, refetch } = useQuery({
    queryKey: ['orders', status, source, pay, q, page],
    queryFn: () => api<{ total: number; items: Order[] }>(
      `/orders?limit=${limit}&offset=${page * limit}` +
      (status ? `&status=${status}` : '') + (source ? `&source=${source}` : '') +
      (pay ? `&payment_status=${pay}` : '') + (q ? `&q=${encodeURIComponent(q)}` : '')),
    refetchInterval: 30000, // нові замовлення з синхронізації підтягуються самі
  });
  useEffect(() => {
    if (!data) return;
    const ids = new Set(data.items.map((o) => o.id));
    if (known.current.size > 0) {
      const added = [...ids].filter((id) => !known.current.has(id));
      if (added.length > 0) {
        setFlash(new Set(added));
        setFresh((n) => n + added.length);
        window.setTimeout(() => setFlash(new Set()), 1500);
        window.setTimeout(() => setFresh(0), 8000);
      }
    }
    known.current = ids;
  }, [data]);
  if (isLoading) return <Card><Skeleton rows={6} /></Card>;
  if (error || !data) return <Card><ErrorState onRetry={() => refetch()} /></Card>;
  const from = data.total === 0 ? 0 : page * limit + 1;
  const to = Math.min((page + 1) * limit, data.total);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <Card style={{ display: 'flex', gap: 10, alignItems: 'end', flexWrap: 'wrap' }}>
        <div>
          <h2 style={{ margin: '0 0 2px', fontSize: 20 }}>Замовлення</h2>
          <div className="num" style={{ color: 'var(--text-muted)', fontSize: 13 }}>
            {data.total === 0 ? 'Поки порожньо' : `${from}–${to} із ${data.total}`}
          </div>
        </div>
        <span style={{ flex: 1 }} />
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: 'var(--text-muted)' }}>
          Статус
          <Select value={status} onChange={(e) => { setStatus(e.target.value); setPage(0); }} aria-label="Статус"
            style={{ minWidth: 160 }}>
            <option value="">Всі статуси</option>
            {['new', 'confirmed', 'packed', 'shipped', 'delivered', 'cancelled', 'returned'].map((s) => (
              <option key={s} value={s}>{t('order.' + s)}</option>))}
          </Select>
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: 'var(--text-muted)' }}>
          Джерело
          <Select value={source} onChange={(e) => { setSource(e.target.value); setPage(0); }} aria-label="Джерело"
            style={{ minWidth: 150 }}>
            <option value="">Всі джерела</option>
            {['prom', 'rozetka', 'site', 'manual'].map((s) => (
              <option key={s} value={s}>{t('source.' + s)}</option>))}
          </Select>
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: 'var(--text-muted)' }}>
          Оплата
          <Select value={pay} onChange={(e) => { setPay(e.target.value); setPage(0); }} aria-label="Оплата"
            style={{ minWidth: 140 }}>
            <option value="">Будь-яка</option>
            {['unpaid', 'paid', 'partial', 'refunded'].map((s) => (
              <option key={s} value={s}>{t('pay.' + s)}</option>))}
          </Select>
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: 'var(--text-muted)' }}>
          Пошук
          <Input value={q} onChange={(e) => { setQ(e.target.value); setPage(0); }}
            placeholder="Номер, ТТН…" aria-label="Пошук замовлень" style={{ minWidth: 150 }} />
        </label>
      </Card>
      {data.items.length === 0 && (
        <Card><EmptyState title="Замовлень ще немає"
          hint="Підключіть магазин або створіть замовлення вручну."
          action={<span style={{ display: 'inline-flex', gap: 8 }}>
            <Link to="/integrations"><Button>Підключити магазин</Button></Link>
            <Link to="/deals"><Button variant="ghost">До угод</Button></Link>
          </span>} /></Card>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(330px,1fr))', gap: 12 }}>
        {data.items.map((o) => (
          <Card key={o.id} style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 10,
            cursor: 'pointer', ...(flash.has(o.id) ? { animation: 'orderFlash 1.2s ease-out' } : {}) }}
            onClick={() => setOpenId(o.id)} role="button" tabIndex={0}
            onKeyDown={(e) => { if (e.key === 'Enter') setOpenId(o.id); }}
            aria-label={`Замовлення ${o.order_number || o.external_id}`}>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <span aria-hidden
                style={{ width: 40, height: 40, borderRadius: 12, flex: 'none',
                  background: 'var(--bg-hover)', color: 'var(--text)',
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
                <Package size={20} />
              </span>
              <div style={{ minWidth: 0 }}>
                <b style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {o.order_number || o.external_id}
                </b>
                <span style={{ display: 'inline-flex', gap: 5, alignItems: 'center',
                  color: 'var(--text-muted)', fontSize: 12 }}>
                  <Store size={13} aria-hidden />{t('source.' + o.source)}
                </span>
              </div>
              <span className="num" style={{ marginLeft: 'auto', fontSize: 18, fontWeight: 800, whiteSpace: 'nowrap' }}>
                {Math.round(o.total).toLocaleString('uk-UA')} {o.currency}
              </span>
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
              <span style={{ display: 'inline-flex', gap: 5, alignItems: 'center', fontSize: 12,
                color: 'var(--text-muted)' }}>
                <Truck size={14} aria-hidden />
                <Badge tone={statusTone(o.status)}>{t('order.' + o.status)}</Badge>
              </span>
              <span style={{ display: 'inline-flex', gap: 5, alignItems: 'center', fontSize: 12,
                color: 'var(--text-muted)' }}>
                <Banknote size={14} aria-hidden />
                <Badge tone={payTone(o.payment_status)}>{t('pay.' + o.payment_status)}</Badge>
              </span>
            </div>
          </Card>
        ))}
      </div>
      {data.total > 0 && (
        <Card style={{ display: 'flex', gap: 8, alignItems: 'center', justifyContent: 'center' }}>
          <Button variant="ghost" disabled={page === 0} onClick={() => setPage((p) => p - 1)}
            aria-label="Попередня сторінка">
            <ChevronLeft size={16} /> Назад
          </Button>
          <span className="num" style={{ color: 'var(--text-muted)', fontSize: 13 }}>
            Сторінка {page + 1} із {Math.max(1, Math.ceil(data.total / limit))}
          </span>
          <Button variant="ghost" disabled={(page + 1) * limit >= data.total} onClick={() => setPage((p) => p + 1)}
            aria-label="Наступна сторінка">
            Вперед <ChevronRight size={16} />
          </Button>
        </Card>
      )}
      {fresh > 0 && page === 0 && (
        <div role="status" className="toast-in"
          style={{ position: 'fixed', bottom: 76, left: '50%', transform: 'translateX(-50%)',
            background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 12,
            padding: '10px 18px', zIndex: 50 }}>
          Нових замовлень: {fresh} — список оновлено
        </div>
      )}
      {openId && <OrderDrawer orderId={openId} onClose={() => setOpenId(null)} />}
    </div>
  );
}
