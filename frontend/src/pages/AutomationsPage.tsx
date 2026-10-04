import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Play, Trash2, Zap } from 'lucide-react';
import { api } from '../api';
import { Badge, Button, Card, EmptyState, ErrorState, Input, Select, Skeleton } from '../components/ui';
import { t } from '../i18n';

type Rule = { id: string; name: string; trigger_type: string; action_type: string; is_active: boolean; priority: number };

const TRIGGERS = ['new_lead', 'deal_stuck', 'payment_received', 'no_response', 'deal_won', 'deal_lost',
  'order_created', 'order_paid', 'order_shipped', 'order_delivered', 'order_returned'];
const ACTIONS = ['assign_manager', 'notify', 'create_ttn', 'send_message', 'request_review', 'move_segment', 'create_task'];

export default function AutomationsPage() {
  const qc = useQueryClient();
  const [msg, setMsg] = useState('');
  const [name, setName] = useState('');
  const [trig, setTrig] = useState(TRIGGERS[0]);
  const [act, setAct] = useState(ACTIONS[1]);
  const rules = useQuery({ queryKey: ['rules'], queryFn: () => api<Rule[]>('/automations/rules') });
  const logs = useQuery({ queryKey: ['auto-logs'], queryFn: () => api<any[]>('/automations/logs') });
  const stats = useQuery({
    queryKey: ['auto-stats'],
    queryFn: () => api<Record<string, Record<string, number>>>('/automations/stats'),
  });

  async function seed() {
    setMsg('');
    try {
      const r = await api<{ created: number }>('/automations/seed-defaults', { method: 'POST' });
      setMsg(`Готово: створено правил: ${r?.created || 0} (повтор не дублює).`);
      qc.invalidateQueries({ queryKey: ['rules'] });
    } catch {
      setMsg('Не вдалося створити правила.');
    }
  }
  async function create() {
    if (!name.trim()) return;
    setMsg('');
    try {
      await api('/automations/rules', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim(), trigger_type: trig, action_type: act }),
      });
      setName('');
      qc.invalidateQueries({ queryKey: ['rules'] });
    } catch {
      setMsg('Не вдалося створити правило.');
    }
  }
  async function remove(id: string) {
    try {
      await api(`/automations/rules/${id}`, { method: 'DELETE' });
      qc.invalidateQueries({ queryKey: ['rules'] });
    } catch {
      setMsg('Не вдалося видалити правило.');
    }
  }

  if (rules.isLoading) return <Card><Skeleton rows={5} /></Card>;
  if (rules.error || !rules.data) return <Card><ErrorState onRetry={() => rules.refetch()} /></Card>;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <Card style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        <Zap size={20} aria-hidden style={{ color: 'var(--warning)' }} />
        <div>
          <b>5 правил одним кліком</b>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            Новий лід → менеджер, завислі → задача, оплата → ТТН, мовчання → лист, виграш → відгук.
          </div>
        </div>
        <span style={{ flex: 1 }} />
        <Button onClick={seed}><Play size={15} /> Запустити 5 правил</Button>
      </Card>
      {msg && <Card style={{ padding: 12 }}>{msg}</Card>}
      <Card>
        <h3>Правила ({rules.data.length})</h3>
        {rules.data.length === 0 && (
          <EmptyState title="Правил поки немає" hint="Запустіть 5 правил кнопкою вище або створіть своє." />
        )}
        {rules.data.map((r) => {
          const st = stats.data?.[r.id];
          const ok = st ? Object.entries(st).reduce((a, [k, v]) => a + (k === 'error' ? 0 : v), 0) : null;
          const err = st?.error || 0;
          return (
            <div key={r.id} style={{ display: 'flex', gap: 10, alignItems: 'center',
              padding: '10px 0', borderTop: '1px solid var(--border)' }}>
              <div style={{ minWidth: 0, flex: 1 }}>
                <b>{r.name}</b>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  Якщо <b>{r.trigger_type}</b> → то <b>{r.action_type}</b>
                  {ok !== null && <> · спрацювало {ok}, помилок {err}</>}
                </div>
              </div>
              <Badge tone={r.is_active ? 'ok' : 'warn'}>{r.is_active ? 'Активне' : 'Вимкнено'}</Badge>
              <Button variant="ghost" onClick={() => remove(r.id)} aria-label={`Видалити ${r.name}`}>
                <Trash2 size={15} />
              </Button>
            </div>
          );
        })}
      </Card>
      <Card>
        <h3>Нове правило</h3>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'end' }}>
          <label style={{ fontSize: 12, color: 'var(--text-muted)' }}>Назва
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Наприклад: Велика угода → адмін" aria-label="Назва правила" />
          </label>
          <label style={{ fontSize: 12, color: 'var(--text-muted)' }}>Якщо
            <Select value={trig} onChange={(e) => setTrig(e.target.value)} aria-label="Тригер">
              {TRIGGERS.map((x) => <option key={x} value={x}>{x}</option>)}
            </Select>
          </label>
          <label style={{ fontSize: 12, color: 'var(--text-muted)' }}>То
            <Select value={act} onChange={(e) => setAct(e.target.value)} aria-label="Дія">
              {ACTIONS.map((x) => <option key={x} value={x}>{x}</option>)}
            </Select>
          </label>
          <Button onClick={create} disabled={!name.trim()}>Створити</Button>
        </div>
      </Card>
      <Card>
        <h3>Журнал спрацювань</h3>
        {logs.isLoading && <Skeleton rows={3} />}
        {logs.error && <ErrorState onRetry={() => logs.refetch()} />}
        {(logs.data || []).length === 0 && !logs.isLoading && !logs.error && (
          <EmptyState title={t('state.empty')} hint="Журнал зʼявиться після перших спрацювань." />
        )}
        {(logs.data || []).slice(0, 15).map((l: any, i: number) => (
          <div key={l.id || i} style={{ display: 'flex', gap: 8, fontSize: 13, padding: '6px 0',
            borderTop: i ? '1px solid var(--border)' : 'none' }}>
            <Badge tone={l.status === 'error' ? 'bad' : 'ok'}>{l.status}</Badge>
            <span style={{ color: 'var(--text-muted)' }}>
              {l.created_at ? new Date(l.created_at).toLocaleString('uk-UA') : ''}
            </span>
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {l.error_message || `rule ${String(l.rule_id || '').slice(0, 8)}`}
            </span>
          </div>
        ))}
      </Card>
    </div>
  );
}
