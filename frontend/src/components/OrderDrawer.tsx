import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Package, Truck, Undo2, X } from 'lucide-react';
import { api } from '../api';
import { Badge, Button, Card, ErrorState, Input, Select, Skeleton } from './ui';
import { t } from '../i18n';

type Item = { sku?: string; name: string; qty: number; unit_price: number; total?: number };
type Ship = { id: string; carrier: string; ttn?: string; status?: string; cod_amount?: number };
type Hist = { from_status?: string; to_status?: string; changed_at?: string; source?: string };
type Ret = { id: string; reason?: string; amount?: number; status?: string };

const FLOW = ['new', 'confirmed', 'packed', 'shipped', 'delivered'];

export default function OrderDrawer({ orderId, onClose }: { orderId: string; onClose: () => void }) {
  const qc = useQueryClient();
  const [status, setStatus] = useState('');
  const [cod, setCod] = useState('');
  const [retReason, setRetReason] = useState('');
  const [retAmount, setRetAmount] = useState('');
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [msg, setMsg] = useState('');
  const { data, error, isLoading, refetch } = useQuery({
    queryKey: ['order', orderId],
    queryFn: () => api<{ order: any; items: Item[]; payments: any[]; shipments: Ship[]; history: Hist[] }>(
      `/orders/${orderId}`),
  });

  async function setOrderStatus() {
    if (!status || status === data?.order?.status) return;
    setMsg('');    try {
      await api(`/orders/${orderId}/status`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      });
      setStatus('');
      qc.invalidateQueries({ queryKey: ['order', orderId] });
      qc.invalidateQueries({ queryKey: ['orders'] });
    } catch {
      setMsg('Не вдалося змінити статус.');
    }
  }
  async function setFixedStatus(next: string, okMsg: string) {
    setMsg('');
    setConfirmCancel(false);
    try {
      await api(`/orders/${orderId}/status`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: next }),
      });
      setMsg(okMsg);
      qc.invalidateQueries({ queryKey: ['order', orderId] });
      qc.invalidateQueries({ queryKey: ['orders'] });
    } catch {
      setMsg('Не вдалося. Спробуйте ще раз.');
    }
  }
  async function createTtn() {
    setMsg('');
    try {
      await api(`/orders/${orderId}/shipments`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ carrier: 'novaposhta', cod_amount: Number(cod) || 0 }),
      });
      setCod('');
      qc.invalidateQueries({ queryKey: ['order', orderId] });
    } catch {
      setMsg('ТТН не створено: підключіть Нову Пошту в інтеграціях.');
    }
  }
  async function createReturn() {
    setMsg('');
    try {
      await api(`/orders/${orderId}/returns`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: retReason, amount: Number(retAmount) || 0 }),
      });
      setRetReason(''); setRetAmount('');
      qc.invalidateQueries({ queryKey: ['order', orderId] });
    } catch {
      setMsg('Не вдалося оформити повернення.');
    }
  }

  return (
    <div onClick={onClose}
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', zIndex: 60,
        display: 'flex', justifyContent: 'flex-end' }}>
      <div className="glass drawer-in" onClick={(e) => e.stopPropagation()}
        style={{ width: 460, maxWidth: '94vw', height: '100%', overflowY: 'auto', padding: 18 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <h2 style={{ margin: 0, flex: 1 }}>Замовлення</h2>
          <button onClick={onClose} aria-label="Закрити" style={xBtn}><X size={18} /></button>
        </div>
        {isLoading && <Skeleton rows={8} />}
        {error && <ErrorState onRetry={() => refetch()} />}
        {data && <Body data={data} status={status} setStatus={setStatus} setOrderStatus={setOrderStatus}
          cancel={() => setFixedStatus('cancelled', 'Замовлення скасовано.')}
          reopen={() => setFixedStatus('new', 'Замовлення повернуто в роботу.')}
          confirmCancel={confirmCancel} setConfirmCancel={setConfirmCancel}
          cod={cod} setCod={setCod} createTtn={createTtn}
          retReason={retReason} setRetReason={setRetReason} retAmount={retAmount}
          setRetAmount={setRetAmount} createReturn={createReturn} msg={msg} />}
      </div>
    </div>
  );
}

const xBtn: React.CSSProperties = {
  background: 'transparent', border: '1px solid var(--border)', borderRadius: 10,
  width: 40, height: 40, display: 'inline-flex', alignItems: 'center',
  justifyContent: 'center', cursor: 'pointer', color: 'var(--text)',
};

function Body(props: {
  data: { order: any; items: Item[]; payments: any[]; shipments: Ship[]; history: Hist[] };
  status: string; setStatus: (v: string) => void; setOrderStatus: () => void;
  cancel: () => void; reopen: () => void;
  confirmCancel: boolean; setConfirmCancel: (v: boolean) => void;
  cod: string; setCod: (v: string) => void; createTtn: () => void;
  retReason: string; setRetReason: (v: string) => void; retAmount: string;
  setRetAmount: (v: string) => void; createReturn: () => void; msg: string;
}) {
  const { data, msg } = props;
  const o = data.order;
  const idx = FLOW.indexOf(o.status);
  const active = !['delivered', 'cancelled', 'returned'].includes(o.status);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 12 }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <b style={{ fontSize: 18 }}>{o.order_number || o.external_id}</b>
        <Badge>{t('source.' + o.source)}</Badge>
        <span className="num" style={{ marginLeft: 'auto', fontSize: 20, fontWeight: 800 }}>
          {Math.round(o.total || 0).toLocaleString('uk-UA')} {o.currency}
        </span>
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        <Badge tone={o.status === 'delivered' ? 'ok' : o.status === 'cancelled' || o.status === 'returned' ? 'bad' : 'info'}>
          {t('order.' + o.status)}
        </Badge>
        <Badge tone={o.payment_status === 'paid' ? 'ok' : 'warn'}>{t('pay.' + o.payment_status)}</Badge>
      </div>

      {idx >= 0 ? (
        <div aria-label="Статус замовлення">
          <div className="step-line">
            {FLOW.map((s, i) => (
              <span key={s} className={'step-dot' + (i <= idx ? ' done' : '') + (i === idx ? ' cur' : '')}
                title={t('order.' + s)}>
                {s === 'shipped' && i <= idx && <Truck size={13} aria-hidden className="truck-run" />}
              </span>
            ))}
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
            {FLOW.map((s) => <span key={s}>{t('order.' + s)}</span>)}
          </div>
        </div>
      ) : (
        <p style={{ color: 'var(--text-muted)' }}>{t('order.' + o.status)}</p>
      )}

      <div style={{ display: 'flex', gap: 8, alignItems: 'end', flexWrap: 'wrap' }}>
        <label style={{ fontSize: 12, color: 'var(--text-muted)' }}>Статус
          <Select value={props.status} onChange={(e) => props.setStatus(e.target.value)} aria-label="Новий статус">
            <option value="">Обрати…</option>
            {['new', 'confirmed', 'packed', 'shipped', 'delivered', 'cancelled', 'returned'].map((s) => (
              <option key={s} value={s}>{t('order.' + s)}</option>))}
          </Select>
        </label>
        <Button variant="ghost" onClick={props.setOrderStatus} disabled={!props.status}>Змінити</Button>
      </div>
      {active ? (
        <div>
          {!props.confirmCancel ? (
            <Button variant="ghost" onClick={() => props.setConfirmCancel(true)}>
              Скасувати замовлення
            </Button>
          ) : (
            <span style={{ display: 'inline-flex', gap: 8, alignItems: 'center', fontSize: 13 }}>
              Точно скасувати? Покупець уже міг оплатити.
              <Button onClick={props.cancel}>Так, скасувати</Button>
              <Button variant="ghost" onClick={() => props.setConfirmCancel(false)}>Ні</Button>
            </span>
          )}
        </div>
      ) : o.status === 'cancelled' ? (
        <div>
          <Button variant="ghost" onClick={props.reopen}>Повернути в роботу</Button>
        </div>
      ) : null}

      <section>
        <h4 style={{ margin: '4px 0 8px', display: 'flex', gap: 6, alignItems: 'center' }}>
          <Package size={15} aria-hidden /> Позиції ({data.items.length})
        </h4>
        {data.items.length === 0 && <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>Без позицій.</p>}
        {data.items.map((it, i) => (
          <div key={i} style={{ display: 'flex', gap: 8, fontSize: 13, padding: '6px 0',
            borderTop: i ? '1px solid var(--border)' : 'none' }}>
            <span style={{ flex: 1 }}>{it.name} <span style={{ color: 'var(--text-muted)' }}>× {it.qty}</span></span>
            <b className="num">{Math.round((it.total ?? it.qty * it.unit_price) || 0).toLocaleString('uk-UA')} ₴</b>
          </div>
        ))}
      </section>

      <section>
        <h4 style={{ margin: '4px 0 8px' }}>Оплати ({data.payments.length})</h4>
        {data.payments.length === 0 && <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>Оплат не зафіксовано.</p>}
        {data.payments.map((p: any, i: number) => (
          <div key={p.id || i} style={{ display: 'flex', gap: 8, fontSize: 13, padding: '5px 0',
            borderTop: i ? '1px solid var(--border)' : 'none' }}>
            <Badge tone={p.status === 'paid' ? 'ok' : 'info'}>{p.status}</Badge>
            <span style={{ color: 'var(--text-muted)' }}>{p.provider}</span>
            <b className="num" style={{ marginLeft: 'auto' }}>
              {Math.round(p.amount || 0).toLocaleString('uk-UA')} ₴</b>
          </div>
        ))}
      </section>

      <section>
        <h4 style={{ margin: '4px 0 8px', display: 'flex', gap: 6, alignItems: 'center' }}>
          <Truck size={15} aria-hidden /> Відправлення ({data.shipments.length})
        </h4>
        {data.shipments.map((s) => (
          <div key={s.id} className="num" style={{ fontSize: 13, padding: '6px 0' }}>
            ТТН: <b>{s.ttn || '—'}</b> <span style={{ color: 'var(--text-muted)' }}>{s.carrier}{s.status ? ` · ${s.status}` : ''}</span>
          </div>
        ))}
        <div style={{ display: 'flex', gap: 8, alignItems: 'end', marginTop: 6, flexWrap: 'wrap' }}>
          <label style={{ fontSize: 12, color: 'var(--text-muted)' }}>Накладений, ₴
            <Input value={props.cod} onChange={(e) => props.setCod(e.target.value)} inputMode="decimal"
              placeholder="0" aria-label="Накладений платіж" style={{ maxWidth: 120 }} />
          </label>
          <Button variant="ghost" onClick={props.createTtn}>Створити ТТН (НП)</Button>
        </div>
      </section>

      <section>
        <h4 style={{ margin: '4px 0 8px', display: 'flex', gap: 6, alignItems: 'center' }}>
          <Undo2 size={15} aria-hidden /> Повернення
        </h4>
        <div style={{ display: 'flex', gap: 8, alignItems: 'end', flexWrap: 'wrap' }}>
          <label style={{ fontSize: 12, color: 'var(--text-muted)' }}>Причина
            <Input value={props.retReason} onChange={(e) => props.setRetReason(e.target.value)}
              placeholder="Наприклад: брак" aria-label="Причина повернення" />
          </label>
          <label style={{ fontSize: 12, color: 'var(--text-muted)' }}>Сума, ₴
            <Input value={props.retAmount} onChange={(e) => props.setRetAmount(e.target.value)}
              inputMode="decimal" placeholder="0" aria-label="Сума повернення" style={{ maxWidth: 110 }} />
          </label>
          <Button variant="ghost" onClick={props.createReturn}>Оформити</Button>
        </div>
      </section>

      <section>
        <h4 style={{ margin: '4px 0 8px' }}>Історія статусів</h4>
        {data.history.length === 0 && <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>Історії поки немає.</p>}
        {data.history.map((h, i) => (
          <div key={i} style={{ fontSize: 13, padding: '5px 0', color: 'var(--text-muted)' }}>
            {h.from_status || '—'} → <b style={{ color: 'var(--text)' }}>{h.to_status}</b>
            {' '}· {h.changed_at || ''}{h.source ? ` · ${h.source}` : ''}
          </div>
        ))}
      </section>
      {msg && <Card style={{ padding: 10, borderLeft: '4px solid var(--warning)' }}>{msg}</Card>}
    </div>
  );
}
