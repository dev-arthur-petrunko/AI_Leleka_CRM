import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Flame, Snowflake, Sun } from 'lucide-react';
import { api } from '../api';
import { useCountUp } from '../hooks/useCountUp';
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

function ColSum({ value }: { value: number }) {
  const v = useCountUp(value);
  return (
    <span className="num">{Math.round(v).toLocaleString('uk-UA')} ₴</span>
  );
}
function PriorityChip({ score }: { score?: number }) {  const s = score ?? 50;
  const Icon = s >= 70 ? Flame : s >= 40 ? Sun : Snowflake;
  const label = s >= 70 ? t('score.hot') : s >= 40 ? t('score.warm') : t('score.cold');
  const tone = s >= 70 ? 'bad' : s >= 40 ? 'warn' : 'info';
  if (s >= 70) {
    return (
      <Badge tone="bad">
        <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
          <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden className="hot-ring">
            <circle cx="7" cy="7" r="5.5" fill="none" stroke="var(--border)" strokeWidth="2" />
            <circle cx="7" cy="7" r="5.5" fill="none" stroke="var(--danger)" strokeWidth="2"
              strokeLinecap="round" className="ring-fg" pathLength={100} />
          </svg>
          {label}
        </span>
      </Badge>
    );
  }
  return <Badge tone={tone as 'bad'}><span style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}><Icon size={12} />{label}</span></Badge>;
}

/** Температура клієнта прямо на угоді: ручна мітка сильніша за скоринг. */
function TempControl({ clientId, temp }: { clientId: string; temp: string }) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const tone = temp === 'hot' ? 'bad' : temp === 'warm' ? 'warn' : temp === 'cold' ? 'info' : undefined;
  return (
    <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}
      onClick={(e) => e.stopPropagation()} onPointerDown={(e) => e.stopPropagation()}>
      {temp ? (
        <Badge tone={tone as 'bad'}>{t('score.' + temp)}</Badge>
      ) : (
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{t('temp.auto')}</span>
      )}
      <select value={temp} aria-label="Температура клієнта" disabled={busy}
        onChange={async (e) => {
          const next = e.target.value;
          setBusy(true);
          try {
            await api(`/clients/${clientId}`, {
              method: 'PATCH', headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ temperature: next }),
            });
            qc.invalidateQueries({ queryKey: ['deal-clients'] });
            qc.invalidateQueries({ queryKey: ['hot-leads'] });
          } catch { /* помилка — селект лишається, видно при рефетчі */ }
          finally {
            setBusy(false);
          }
        }}
        style={{ fontSize: 11, padding: '4px 6px', borderRadius: 8,
          border: '1px solid var(--border)', background: 'var(--bg)',
          color: 'var(--text)', cursor: 'pointer', maxWidth: 110 }}>
        <option value="">{t('temp.auto')}</option>
        {(['hot', 'warm', 'cold'] as const).map((s) => (
          <option key={s} value={s}>{t('score.' + s)}</option>))}
      </select>
    </span>
  );
}

export default function Deals() {
  const [view, setView] = useState<'kanban' | 'table'>('kanban');
  const [q, setQ] = useState('');
  const [mine, setMine] = useState(false);
  const [convertFor, setConvertFor] = useState<Deal | null>(null);
  const [convertErr, setConvertErr] = useState('');
  const [lossFor, setLossFor] = useState<Deal | null>(null);
  const [lossReason, setLossReason] = useState<string>(LOSS_REASONS[0]);
  const [over, setOver] = useState<{ col: string; index: number } | null>(null);
  const [creating, setCreating] = useState(false);
  const [newClient, setNewClient] = useState('');
  const [newTitle, setNewTitle] = useState('');
  const [newAmount, setNewAmount] = useState('');
  const [createErr, setCreateErr] = useState('');
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<Deal | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editAmount, setEditAmount] = useState('');
  const [editClient, setEditClient] = useState('');
  const [editErr, setEditErr] = useState('');

  const dragRef = useRef<null | {
    id: string; el: HTMLElement; x0: number; y0: number; active: boolean;
    raf: number; cx: number; cy: number;
  }>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const suppressClick = useRef(false);

  // Pointer-DnD: працює мишею і тачем (нативний HTML5-DnD на тачі мовчить,
  // а ре-рендер у dragstart обриває перетягування в Chrome).
  function colIndexAt(colEl: HTMLElement, clientY: number, selfId: string): number {
    const els = Array.from(colEl.querySelectorAll<HTMLElement>('[data-deal]'))
      .filter((el) => el.dataset.deal !== selfId);
    for (let i = 0; i < els.length; i++) {
      const r = els[i].getBoundingClientRect();
      if (clientY < r.top + r.height / 2) return i;
    }
    return els.length;
  }
  function colAt(clientX: number, clientY: number): { col: string; el: HTMLElement } | null {
    const els = document.elementsFromPoint(clientX, clientY) as HTMLElement[];
    for (const el of els) {
      const c = el.closest?.('[data-col]') as HTMLElement | null;
      if (c && c.dataset.col) return { col: c.dataset.col, el: c };
    }
    return null;
  }
  function paintDrag() {
    const dr = dragRef.current;
    if (!dr?.active) return;
    dr.raf = 0;
    // картка їде за пальцем/курсором напряму в DOM — без ре-рендерів
    const dx = dr.cx - dr.x0, dy = dr.cy - dr.y0;
    dr.el.style.transition = 'none';
    dr.el.style.transform = `translate(${dx}px, ${dy}px) rotate(2deg) scale(1.04)`;
    dr.el.style.boxShadow = '0 12px 26px rgba(0,0,0,.3)';
    dr.el.style.opacity = '0.9';
    dr.el.style.zIndex = '50';
    dr.el.style.pointerEvents = 'none';
    dr.el.style.cursor = 'grabbing';
    const hit = colAt(dr.cx, dr.cy);
    if (hit) setOver({ col: hit.col, index: colIndexAt(hit.el, dr.cy, dr.id) });
    else setOver(null);
    const sc = scrollRef.current;
    if (sc) {
      const r = sc.getBoundingClientRect();
      if (dr.cx > r.right - 48) sc.scrollLeft += 14;
      else if (dr.cx < r.left + 48) sc.scrollLeft -= 14;
    }
  }
  function onDragMove(e: PointerEvent) {
    const dr = dragRef.current;
    if (!dr) return;
    if (!dr.active) {
      if (Math.hypot(e.clientX - dr.x0, e.clientY - dr.y0) < 8) return;
      dr.active = true;
      document.body.style.userSelect = 'none';
      document.body.style.cursor = 'grabbing';
    }
    if (e.cancelable) e.preventDefault();
    dr.cx = e.clientX;
    dr.cy = e.clientY;
    if (!dr.raf) dr.raf = requestAnimationFrame(paintDrag);
  }
  function endDrag(e: PointerEvent) {
    const dr = dragRef.current;
    dragRef.current = null;
    window.removeEventListener('pointermove', onDragMove);
    if (dr?.raf) cancelAnimationFrame(dr.raf);
    if (dr) {
      // повертаємо картку під React-стилі з мʼякою посадкою
      dr.el.style.transition = 'transform var(--dur-200,200ms) var(--ease-out, ease-out), box-shadow var(--dur-200,200ms), opacity var(--dur-200,200ms)';
      dr.el.style.transform = '';
      dr.el.style.boxShadow = '';
      dr.el.style.opacity = '';
      dr.el.style.zIndex = '';
      dr.el.style.pointerEvents = '';
      dr.el.style.cursor = '';
    }
    document.body.style.userSelect = '';
    document.body.style.cursor = '';
    setOver(null);
    if (!dr?.active) return;
    // клік після перетягування не має відкривати редактор
    suppressClick.current = true;
    window.setTimeout(() => { suppressClick.current = false; }, 0);
    const hit = colAt(e.clientX, e.clientY);
    if (!hit) return;
    const cur = data?.items.find((x) => x.id === dr.id)?.stage;
    if (!cur || cur === hit.col) return;
    if (hit.col === 'lost') {
      const dd = data?.items.find((x) => x.id === dr.id);
      if (dd) setLossFor(dd);
    } else {
      const el = document.querySelector(`[data-deal="${dr.id}"]`) as HTMLElement | null;
      move(dr.id, hit.col, { userInitiated: true, el });
    }
  }
  function onCardPointerDown(e: React.PointerEvent, deal: Deal) {
    if (e.pointerType === 'mouse' && e.button !== 0) return;
    if ((e.target as HTMLElement).closest('button,input,select,a')) return;
    dragRef.current = { id: deal.id, el: e.currentTarget as HTMLElement, x0: e.clientX, y0: e.clientY,
      active: false, raf: 0, cx: e.clientX, cy: e.clientY };
    window.addEventListener('pointermove', onDragMove);
    window.addEventListener('pointerup', endDrag, { once: true });
    window.addEventListener('pointercancel', endDrag, { once: true });
  }
  useEffect(() => () => {
    window.removeEventListener('pointermove', onDragMove);
    dragRef.current = null;
  }, []);
  const [undo, setUndo] = useState<null | { id: string; prev: string }>(null);
  const qc = useQueryClient();
  const celebration = useDealWonCelebration();
  const me = useQuery({ queryKey: ['me'], queryFn: () => api<{ id: string }>('/auth/me') });
  const { data, error, isLoading, refetch } = useQuery({
    queryKey: ['deals', mine, me.data?.id],
    queryFn: () => api<{ total: number; items: Deal[] }>(
      `/deals?limit=200${mine && me.data?.id ? `&manager_id=${me.data.id}` : ''}`),
  });
  const clients = useQuery({
    queryKey: ['deal-clients'],
    queryFn: () => api<{ total: number; items: { id: string; name: string; temperature?: string | null }[] }>('/clients?limit=200'),
  });
  const tempOf = (clientId: string) =>
    clients.data?.items.find((c) => c.id === clientId)?.temperature || '';
  const nameOf = (clientId: string) =>
    clients.data?.items.find((c) => c.id === clientId)?.name || '';
  const [linkMenu, setLinkMenu] = useState<string | null>(null);
  const [linkConfirm, setLinkConfirm] = useState(false);
  const [linkErr, setLinkErr] = useState('');
  const nav = useNavigate();

  async function doUnlink(d: Deal) {
    setLinkErr('');
    try {
      await api(`/deals/${d.id}/unlink-order`, { method: 'POST' });
      setLinkMenu(null);
      setLinkConfirm(false);
      qc.invalidateQueries({ queryKey: ['deals'] });
    } catch {
      setLinkErr('Не вдалося розірвати звʼязок.');
    }
  }
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
    qc.setQueryData(['deals', mine, me.data?.id], (old: any) => ({
      ...old, items: old.items.map((d: Deal) => (d.id === id ? { ...d, stage } : d)),
    }));
    try {
      await api(`/deals/${id}/stage?stage=${stage}${opts.loss_reason ? `&loss_reason=${encodeURIComponent(opts.loss_reason)}` : ''}`, { method: 'PATCH' });
    } catch {
      qc.setQueryData(['deals', mine, me.data?.id], (old: any) => ({
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
    setConvertErr('');
    try {
      await api<{ order_id: string }>(`/deals/${convertFor.id}/convert-to-order`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}),
      });
      setConvertFor(null);
      qc.invalidateQueries({ queryKey: ['deals'] });
    } catch {
      setConvertErr('Не вдалося створити замовлення. Спробуйте ще раз.');
    }
  }

  function openEdit(d: Deal) {
    setEditing(d);
    setEditTitle(d.title.replace(/^Замовлення\s*#?/, 'Угода #'));
    setEditAmount(String(Math.round(d.amount || 0)));
    setEditClient(d.client_id || '');
    setEditErr('');
  }

  async function doSave() {
    if (!editing || !editTitle.trim() || busy) return;
    setEditErr('');
    setBusy(true);
    try {
      await api(`/deals/${editing.id}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: editTitle.trim(),
          amount: Number(editAmount) || 0,
          ...(editClient ? { client_id: editClient } : {}),
        }),
      });
      setEditing(null);
      qc.invalidateQueries({ queryKey: ['deals'] });
    } catch {
      setEditErr('Не вдалося зберегти. Перевірте назву і суму.');
    } finally {
      setBusy(false);
    }
  }

  async function doCreate() {
    if (!newClient || !newTitle.trim() || busy) return;
    setCreateErr('');
    setBusy(true);
    try {
      await api('/deals', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          client_id: newClient, title: newTitle.trim(),
          amount: Number(newAmount) || 0,
          manager_id: me.data?.id || null,
        }),
      });
      setCreating(false);
      setNewClient(''); setNewTitle(''); setNewAmount('');
      qc.invalidateQueries({ queryKey: ['deals'] });
    } catch {
      setCreateErr('Не вдалося створити угоду. Спробуйте ще раз.');
    } finally {
      setBusy(false);
    }
  }

  if (isLoading) return <Card><Skeleton rows={6} /></Card>;
  if (error || !data) return <Card><ErrorState onRetry={() => refetch()} /></Card>;
  let deals = data.items;
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
        <Button onClick={() => { setCreating(true); setCreateErr(''); }}>+ Угода</Button>
      </div>
      {views.data && views.data.length > 0 && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
          {views.data.map((v: any) => (
            <button key={v.id} onClick={() => {
              const f = v.filters || {};
              if (typeof f.q === 'string') setQ(f.q);
              if (typeof f.mine === 'boolean') setMine(f.mine);
            }}
              title="Застосувати вид"
              style={{ padding: '6px 12px', borderRadius: 16, border: '1px solid var(--border)',
                background: 'transparent', color: 'var(--text)', cursor: 'pointer', fontSize: 12 }}>
              {v.name}
            </button>))}
          <button onClick={async () => {
            const name = window.prompt('Назва виду (збереже поточні пошук і «Мої»):');
            if (!name?.trim()) return;
            try {
              await api('/views', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ entity: 'deals', name: name.trim(), filters: { q, mine } }),
              });
              views.refetch();
            } catch { /* ignore */ }
          }}
            title="Зберегти поточні фільтри як вид"
            style={{ padding: '6px 12px', borderRadius: 16, border: '1px dashed var(--border)',
              background: 'transparent', color: 'var(--link)', cursor: 'pointer', fontSize: 12 }}>
            + вид
          </button>
        </div>
      )}
      {deals.length === 0 && (
        <Card><EmptyState title="Угод немає" hint="Створіть першу угоду кнопкою вище." /></Card>
      )}
      {view === 'kanban' ? (
        <div ref={scrollRef} style={{ display: 'grid', gridTemplateColumns: 'repeat(5,minmax(240px,300px))', gap: 12, overflowX: 'auto', alignItems: 'start' }}>
          {STAGES.map((s) => {
            const col = deals.filter((d) => d.stage === s);
            const sum = col.reduce((a, d) => a + d.amount, 0);
            const wsum = col.reduce((a, d) => a + d.amount * (STAGE_PROB[s] / 100), 0);
            return (
              <div key={s} className="glass" data-col={s}
                style={{ padding: 10, minHeight: 220, borderTop: `4px solid ${STAGE_COLOR[s]}`,
                  outline: over?.col === s ? '2px dashed var(--link)' : 'none',
                  transition: 'outline var(--dur-150,150ms) var(--ease-out, ease-out)' }}>
                <h4 title={`Взвішена: ${Math.round(wsum).toLocaleString('uk-UA')} ₴`}>
                  {t('stage.' + s)} · {col.length} · <ColSum value={sum} />
                </h4>
                {col.length === 0 && !(over?.col === s) && (
                  <div style={{ border: '1.5px dashed var(--border)', borderRadius: 10, padding: 16,
                    textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>Перетягніть сюди</div>
                )}
                {col.flatMap((d, i) => {
                  const card = (
                    <div key={d.id} data-deal={d.id}
                      className="glass card-in lift"
                      onPointerDown={(e) => onCardPointerDown(e, d)}
                      onClick={() => { if (!suppressClick.current) openEdit(d); }}
                      style={{ padding: 11, marginBottom: 9, cursor: 'grab', touchAction: 'pan-y',
                        '--i': i % 8,
                        borderLeft: `4px solid ${d.stage === 'won' ? 'var(--stage-won)' : 'var(--stage-negotiation)'}` } as CSSProperties}>
                      <b>{d.title.replace(/^Замовлення\s*#?/, 'Угода #')}</b>
                      {nameOf(d.client_id) && (
                        <div style={{ fontSize: 11, color: 'var(--text-muted)',
                          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {nameOf(d.client_id)}
                        </div>
                      )}
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{d.id.slice(0, 8)}</div>
                      <div style={{ margin: '6px 0', display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                        <PriorityChip score={scoreOf(d.id)} />
                        <TempControl clientId={d.client_id} temp={tempOf(d.client_id)} />
                      </div>
                      <div className="num" style={{ fontSize: 19, fontWeight: 800 }}>
                        {Math.round(d.amount).toLocaleString('uk-UA')} ₴</div>
                      {d.stage === 'won' && !d.converted_order_id && (
                        <button onClick={(e) => { e.stopPropagation(); setConvertFor(d); }}>→ замовлення</button>
                      )}
                      {d.converted_order_id && (
                        <button onClick={(e) => {
                          e.stopPropagation();
                          setLinkMenu(linkMenu === d.id ? null : d.id);
                          setLinkConfirm(false);
                          setLinkErr('');
                        }}
                          style={{ background: 'var(--success)', color: 'var(--primary-fg)',
                            border: 'none', borderRadius: 12, padding: '3px 10px',
                            fontSize: 12, fontWeight: 700, cursor: 'pointer' }}>
                          Замовлення ✓
                        </button>
                      )}
                      {linkMenu === d.id && (
                        <div onClick={(e) => e.stopPropagation()}
                          style={{ marginTop: 6, padding: 8, borderRadius: 8,
                            background: 'var(--bg-hover)', display: 'flex',
                            flexDirection: 'column', gap: 6 }}>
                          {!linkConfirm ? (
                            <>
                              <button onClick={() => nav(`/orders?order=${d.converted_order_id}`)}>
                                Відкрити замовлення
                              </button>
                              <button onClick={() => setLinkConfirm(true)}>
                                Розірвати звʼязок
                              </button>
                            </>
                          ) : (
                            <>
                              <span style={{ fontSize: 12 }}>
                                Прибрати звʼязок? Замовлення лишиться у списку.
                              </span>
                              <span style={{ display: 'flex', gap: 6 }}>
                                <button onClick={() => doUnlink(d)}>Так</button>
                                <button onClick={() => setLinkConfirm(false)}>Ні</button>
                              </span>
                            </>
                          )}
                          {linkErr && <span style={{ fontSize: 12, color: 'var(--danger)' }}>{linkErr}</span>}
                        </div>
                      )}
                    </div>
                  );
                  const ph = (over?.col === s && over.index === i) ? (
                    <div key={'ph-' + d.id} className="ph" />
                  ) : null;
                  return [ph, card];
                })}
                {over?.col === s && over.index >= col.length && (
                  <div className="ph" />
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <Card>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
            <thead><tr><th>Назва</th><th>Стадія</th><th>Сума</th><th>Температура</th><th></th></tr></thead>
            <tbody>
              {deals.map((d) => (
                <tr key={d.id} style={{ borderTop: '1px solid var(--border)', cursor: 'pointer' }}
                  onClick={() => openEdit(d)}>
                  <td>
                    <div>{d.title}</div>
                    {nameOf(d.client_id) && (
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{nameOf(d.client_id)}</div>
                    )}
                  </td>
                  <td>
                    <Select value={d.stage} aria-label={`Стадія ${d.title}`}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => {
                        const ns = e.target.value;
                        if (ns === d.stage) return;
                        if (ns === 'lost') setLossFor(d);
                        else move(d.id, ns, { userInitiated: true });
                      }}>
                      {STAGES.map((s) => <option key={s} value={s}>{t('stage.' + s)}</option>)}
                    </Select>
                  </td>
                  <td className="num">{Math.round(d.amount).toLocaleString('uk-UA')} ₴</td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <TempControl clientId={d.client_id} temp={tempOf(d.client_id)} />
                  </td>
                  <td>{d.stage === 'won' && !d.converted_order_id && (
                    <button onClick={(e) => { e.stopPropagation(); setConvertFor(d); }}>→ замовлення</button>)}
                    {d.converted_order_id && (
                      <span style={{ display: 'inline-flex', gap: 4 }}>
                        <button onClick={(e) => {
                          e.stopPropagation();
                          nav(`/orders?order=${d.converted_order_id}`);
                        }}>Замовлення ✓</button>
                        <button onClick={(e) => { e.stopPropagation(); doUnlink(d); }}
                          title="Розірвати звʼязок (замовлення лишиться)">✕</button>
                      </span>
                    )}</td>
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
            {convertErr && <p style={{ color: 'var(--danger)' }}>{convertErr}</p>}
            <div style={{ display: 'flex', gap: 8 }}>
              <Button onClick={doConvert}>Створити</Button>
              <Button variant="ghost" onClick={() => { setConvertFor(null); setConvertErr(''); }}>Скасувати</Button>
            </div>
          </div>
        </div>
      )}
      {creating && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', zIndex: 60,
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
          <div key={createErr || 'ok'} className={'glass drawer-in' + (createErr ? ' shake' : '')}
            onClick={(e) => e.stopPropagation()}
            style={{ padding: 22, maxWidth: 400, width: '100%' }}>
            <h3>Нова угода</h3>
            <label style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
              Клієнт
              <Select value={newClient} onChange={(e) => setNewClient(e.target.value)}
                aria-label="Клієнт" style={{ width: '100%', marginTop: 4 }}>
                <option value="">Оберіть клієнта…</option>
                {(clients.data?.items || []).map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>))}
              </Select>
            </label>
            <label style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)', marginTop: 10 }}>
              Назва
              <Input value={newTitle} onChange={(e) => setNewTitle(e.target.value)}
                placeholder="Наприклад: Угода #413 — холодильник" aria-label="Назва угоди"
                style={{ marginTop: 4 }} />
            </label>
            <label style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)', marginTop: 10 }}>
              Сума, ₴
              <Input value={newAmount} onChange={(e) => setNewAmount(e.target.value)}
                inputMode="decimal" placeholder="0" aria-label="Сума" style={{ marginTop: 4 }} />
            </label>
            {createErr && <p style={{ color: 'var(--danger)' }}>{createErr}</p>}
            <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
              <Button onClick={doCreate} disabled={busy || !newClient || !newTitle.trim()}
                style={{ minWidth: 130 }}>
                {busy ? <span className="spin" aria-hidden /> : 'Створити'}
              </Button>
              <Button variant="ghost" onClick={() => setCreating(false)}>Скасувати</Button>
            </div>
          </div>
        </div>
      )}
      {editing && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', zIndex: 60,
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}
          onClick={() => setEditing(null)}>
          <div key={editErr || 'ok'} className={'glass drawer-in' + (editErr ? ' shake' : '')}
            onClick={(e) => e.stopPropagation()}
            style={{ padding: 22, maxWidth: 400, width: '100%' }}>
            <h3>Редагувати угоду</h3>
            <label style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)' }}>
              Назва
              <Input value={editTitle} onChange={(e) => setEditTitle(e.target.value)}
                aria-label="Назва угоди" style={{ marginTop: 4 }} />
            </label>
            <label style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)', marginTop: 10 }}>
              Сума, ₴
              <Input value={editAmount} onChange={(e) => setEditAmount(e.target.value)}
                inputMode="decimal" aria-label="Сума" style={{ marginTop: 4 }} />
            </label>
            <label style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)', marginTop: 10 }}>
              Клієнт
              <Select value={editClient} onChange={(e) => setEditClient(e.target.value)}
                aria-label="Клієнт" style={{ width: '100%', marginTop: 4 }}>
                <option value="">Без змін</option>
                {(clients.data?.items || []).map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>))}
              </Select>
            </label>
            <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              Стадія: {t('stage.' + editing.stage)} (змінюється перетягуванням або зі списку).
            </p>
            {editErr && <p style={{ color: 'var(--danger)' }}>{editErr}</p>}
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <Button onClick={doSave} disabled={busy || !editTitle.trim()}
                style={{ minWidth: 130 }}>
                {busy ? <span className="spin" aria-hidden /> : 'Зберегти'}
              </Button>
              <Button variant="ghost" onClick={() => setEditing(null)}>Скасувати</Button>
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
