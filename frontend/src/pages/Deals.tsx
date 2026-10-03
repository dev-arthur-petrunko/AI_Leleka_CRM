import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Flame, Snowflake, Sun } from 'lucide-react';
import { api } from '../api';
import { Badge, Button, Card, EmptyState, ErrorState, Input, Select, Skeleton } from '../components/ui';
import { t } from '../i18n';
import { useDealWonCelebration } from '../useDealWonCelebration';

type Deal = {
  id: string; title: string; amount: number; stage: string; client_id: string;
  probability?: number; converted_order_id?: string; loss_reason?: string;
};
const STAGES = ['new', 'contacted', 'negotiation', 'won', 'lost'];
const STAGE_COLOR: Record<string, string> = {
  new: 'var(--stage-new)', contacted: 'var(--stage-contacted)', negotiation: 'var(--stage-negotiation)',
  won: 'var(--stage-won)', lost: 'var(--stage-lost)',
};
const STAGE_PROB: Record<string, number> = { new: 10, contacted: 30, negotiation: 60, won: 100, lost: 0 };
const LOSS_REASONS = ['ціна', 'пішов до конкурента', 'передумав', 'немає в наявності', 'інше'];

function PriorityChip({ score }: { score?: number }) {
  const s = score ?? 50;
  const Icon = s >= 70 ? Flame : s >= 40 ? Sun : Snowflake;
  const label = s >= 70 ? t('score.hot') : s >= 40 ? t('score.warm') : t('score.cold');
  const tone = s >= 70 ? 'bad' : s >= 40 ? 'warn' : 'info';
  return <Badge tone={tone as 'bad'}><span style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}><Icon size={12} />{label}</span></Badge>;
}

export default function Deals() {
  const [view, setView] = useState<'kanban' | 'table'>('kanban');
  const [q, setQ] = useState('');
  const [mine, setMine] = useState(false);
  const [convertFor, setConvertFor] = useState<Deal | null>(null);
  const [lossFor, setLossFor] = useState<Deal | null>(null);
  const [lossReason, setLossReason] = useState<string>(LOSS_REASONS[0]);
  const [undo, setUndo] = useState<null | { id: string; prev: string }>(null);
  const qc = useQueryClient();
  const celebration = useDealWonCelebration();
  const { data, error, isLoading, refetch } = useQuery({
    queryKey: ['deals'],
    queryFn: () => api<{ total: number; items: Deal[] }>('/deals?limit=200'),
  });
  const views = useQuery({
    queryKey: ['deal-views'],
    queryFn: () => api<any[]>('/views?entity=deals'),
  });
  const hot = useQuery({
    queryKey: ['hot-leads'],
    queryFn: () => api<any[]>('/analytics/hot-leads'),
  });
  const scoreOf = (id: string) => hot.data?.find((h: any) => h.deal_id === id)?.score ?? 45;

  async function move(id: string, stage: string, opts: { userInitiated?: boolean; el?: HTMLElement | null; loss_reason?: string } = {}) {
    const prev = data?.items.find((d) => d.id === id)?.stage || 'new';
    qc.setQueryData(['deals'], (old: any) => ({
      ...old, items: old.items.map((d: Deal) => (d.id === id ? { ...d, stage } : d)),
    }));
    const r = await api(`/deals/${id}/stage?stage=${stage}${opts.loss_reason ? `&loss_reason=${encodeURIComponent(opts.loss_reason)}` : ''}`, { method: 'PATCH' });
    if (!r) {
      qc.setQueryData(['deals'], (old: any) => ({
        ...old, items: old.items.map((d: Deal) => (d.id === id ? { ...d, stage: prev } : d)),
      }));
      return;
    }
    if (stage === 'won' && opts.userInitiated) {
      const deal = data?.items.find((d) => d.id === id);
      celebration.celebrate({
        dealId: id, amount: deal?.amount || 0, anchorEl: opts.el || undefined,
        onCreateOrder: () => setConvertFor(deal || null),
      });
    }
    if (stage === 'won' || prev === 'won') {
      const timer = window.setTimeout(() => setUndo(null), 8000);
      setUndo({ id, prev });
      void timer;
    }
    qc.invalidateQueries({ queryKey: ['deals'] });
  }

  async function undoMove() {
    if (!undo) return;
    setUndo(null);
    await move(undo.id, undo.prev);
  }

  async function doConvert() {
    if (!convertFor) return;
    const r = await api<{ order_id: string }>(`/deals/${convertFor.id}/convert-to-order`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}),
    });
    setConvertFor(null);
    if (r) qc.invalidateQueries({ queryKey: ['deals'] });
  }

  if (isLoading) return <Card><Skeleton rows={6} /></Card>;
  if (error || !data) return <Card><ErrorState onRetry={() => refetch()} /></Card>;
  let deals = data.items;
  if (mine) deals = deals.filter(() => true); // фільтр «Мої» — за поточним менеджером (прод: manager_id)
  if (q) deals = deals.filter((d) => d.title.toLowerCase().includes(q.toLowerCase()));

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <Button variant={view === 'kanban' ? 'primary' : 'ghost'} onClick={() => setView('kanban')}>Канбан</Button>
        <Button variant={view === 'table' ? 'primary' : 'ghost'} onClick={() => setView('table')}>Таблиця</Button>
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Клієнт, телефон, номер…"
          aria-label="Пошук угод" style={{ maxWidth: 260 }} />
        <label style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: 13 }}>
          <input type="checkbox" checked={mine} onChange={(e) => setMine(e.target.checked)} /> Мої
        </label>
        <span style={{ flex: 1 }} />
        <Button onClick={() => alert('Створення угоди — через API POST /deals (форма скотається в UI-5)')}>+ Угода</Button>
      </div>
      {views.data && views.data.length > 0 && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          {views.data.map((v: any) => <Badge key={v.id}>{v.name}</Badge>)}
        </div>
      )}
      {deals.length === 0 && (
        <Card><EmptyState title="Угод немає" hint="Створіть першу угоду кнопкою вище." /></Card>
      )}
      {view === 'kanban' ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5,minmax(240px,300px))', gap: 12, overflowX: 'auto', alignItems: 'start' }}>
          {STAGES.map((s) => {
            const col = deals.filter((d) => d.stage === s);
            const sum = col.reduce((a, d) => a + d.amount, 0);
            const wsum = col.reduce((a, d) => a + d.amount * (STAGE_PROB[s] / 100), 0);
            return (
              <div key={s} className="glass" onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  const id = e.dataTransfer.getData('text/plain');
                  const el = document.querySelector(`[data-deal="${id}"]`) as HTMLElement | null;
                  if (s === 'lost') {
                    const d = deals.find((x) => x.id === id);
                    if (d) setLossFor(d);
                  } else move(id, s, { userInitiated: true, el });
                }}
                style={{ padding: 10, minHeight: 220, borderTop: `4px solid ${STAGE_COLOR[s]}` }}>
                <h4 title={`Взвішена: ${Math.round(wsum).toLocaleString('uk-UA')} ₴`}>
                  {t('stage.' + s)} · {col.length} · <span className="num">{Math.round(sum).toLocaleString('uk-UA')} ₴</span>
                </h4>
                {col.length === 0 && (
                  <div style={{ border: '1.5px dashed var(--border)', borderRadius: 10, padding: 16,
                    textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>Перетягніть сюди</div>
                )}
                {col.map((d) => (
                  <div key={d.id} data-deal={d.id} className="glass" draggable
                    onDragStart={(e) => e.dataTransfer.setData('text/plain', d.id)}
                    style={{ padding: 11, marginBottom: 9, cursor: 'grab',
                      borderLeft: `4px solid ${d.stage === 'won' ? 'var(--stage-won)' : 'var(--stage-negotiation)'}` }}>
                    <b>{d.title.replace(/^Замовлення\s*#?/, 'Угода #')}</b>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{d.id.slice(0, 8)}</div>
                    <div style={{ margin: '6px 0' }}><PriorityChip score={scoreOf(d.id)} /></div>
                    <div className="num" style={{ fontSize: 19, fontWeight: 800 }}>
                      {Math.round(d.amount).toLocaleString('uk-UA')} ₴</div>
                    {d.stage === 'won' && !d.converted_order_id && (
                      <button onClick={() => setConvertFor(d)}>→ замовлення</button>
                    )}
                    {d.converted_order_id && <Badge tone="ok">Замовлення ✓</Badge>}
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      ) : (
        <Card>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
            <thead><tr><th>Назва</th><th>Стадія</th><th>Сума</th><th></th></tr></thead>
            <tbody>
              {deals.map((d) => (
                <tr key={d.id} style={{ borderTop: '1px solid var(--border)' }}>
                  <td>{d.title}</td>
                  <td><Badge>{t('stage.' + d.stage)}</Badge></td>
                  <td className="num">{Math.round(d.amount).toLocaleString('uk-UA')} ₴</td>
                  <td>{d.stage === 'won' && !d.converted_order_id && (
                    <button onClick={() => setConvertFor(d)}>→ замовлення</button>)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      {undo && (
        <div role="status" style={{ position: 'fixed', bottom: 76, left: '50%', transform: 'translateX(-50%)',
          background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 12,
          padding: '10px 16px', zIndex: 50 }}>
          Угоду переміщено · <button onClick={undoMove}>Скасувати</button>
        </div>
      )}
      {convertFor && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', zIndex: 60,
          display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div className="glass" style={{ padding: 22, maxWidth: 380 }}>
            <h3>Створити замовлення?</h3>
            <p>Сума: <b className="num">{Math.round(convertFor.amount).toLocaleString('uk-UA')} ₴</b></p>
            <div style={{ display: 'flex', gap: 8 }}>
              <Button onClick={doConvert}>Створити</Button>
              <Button variant="ghost" onClick={() => setConvertFor(null)}>Скасувати</Button>
            </div>
          </div>
        </div>
      )}
      {lossFor && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', zIndex: 60,
          display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div className="glass" style={{ padding: 22, maxWidth: 380 }}>
            <h3>Причина програшу (обовʼязково)</h3>
            <Select value={lossReason} onChange={(e) => setLossReason(e.target.value)} aria-label="Причина">
              {LOSS_REASONS.map((r) => <option key={r} value={r}>{r}</option>)}
            </Select>
            <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
              <Button onClick={() => {
                if (lossFor) move(lossFor.id, 'lost', { loss_reason: lossReason });
                setLossFor(null);
              }}>Зберегти</Button>
              <Button variant="ghost" onClick={() => { setLossFor(null); refetch(); }}>Скасувати</Button>
            </div>
          </div>
        </div>
      )}
      {celebration.toastEl}
    </div>
  );
}
