import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Crown, UserPlus } from 'lucide-react';
import { api, HttpError } from '../api';
import { Badge, Button, Card, EmptyState, ErrorState, Input, Select, Skeleton } from '../components/ui';

export default function BillingPage() {
  const qc = useQueryClient();
  const [msg, setMsg] = useState('');
  const [upgradeRes, setUpgradeRes] = useState<any>(null);
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [role, setRole] = useState('manager');
  const [inviteRes, setInviteRes] = useState('');
  const plans = useQuery({ queryKey: ['plans'], queryFn: () => api<Record<string, any>>('/billing/plans') });
  const bills = useQuery({ queryKey: ['bills'], queryFn: () => api<any[]>('/billing/orders') });
  const current = useQuery({ queryKey: ['billing'], queryFn: () => api<any>('/billing/current') });

  async function upgrade(plan: string) {
    setMsg('');
    setUpgradeRes(null);
    try {
      const r = await api<any>('/billing/upgrade', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_plan: plan, provider: 'liqpay' }),
      });
      if (r && r.payment_required) {
        setMsg(`Рахунок на ${r.amount_uah} ₴ створено (замовлення ${r.order_id}).`);
        setUpgradeRes(r);
      } else {
        setMsg(`Тариф змінено: ${r?.plan || plan}.`);
      }
      qc.invalidateQueries({ queryKey: ['billing'] });
      qc.invalidateQueries({ queryKey: ['bills'] });
    } catch (e) {
      if (e instanceof HttpError && e.status === 409) {
        setMsg('Оплата не налаштована власником сервісу — зверніться до підтримки.');
      } else if (e instanceof HttpError && e.status === 403) {
        setMsg('Апгрейд доступний тільки власнику компанії.');
      } else {
        setMsg('Не вдалося змінити тариф.');
      }
    }
  }
  async function invite() {
    setInviteRes('');
    if (!email.trim()) return;
    try {
      const r = await api<any>('/auth/invite', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), full_name: fullName.trim() || email.trim(), role }),
      });
      setInviteRes(`Запрошено ${r?.email}. Тимчасовий пароль: ${r?.temp_password} — передайте колезі, він змінить його при вході.`);
      setEmail(''); setFullName('');
    } catch {
      setInviteRes('Не вдалося запросити (тільки owner/admin, перевірте ліміт місць).');
    }
  }

  if (plans.isLoading || current.isLoading) return <Card><Skeleton rows={5} /></Card>;
  if (plans.error || current.error || !plans.data || !current.data) {
    return <Card><ErrorState onRetry={() => { plans.refetch(); current.refetch(); }} /></Card>;
  }
  const entries = Object.entries(plans.data);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <Card>
        <h3 style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <Crown size={18} aria-hidden /> Поточний тариф: {current.data.label || current.data.plan}
        </h3>
        <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
          Місць зайнято: <b className="num">{current.data.seats_used}</b> із {current.data.seats_limit} ·
          Разом/міс: <b className="num">{current.data.monthly_total_uah} ₴</b>
        </div>
        <div style={{ fontSize: 13, marginTop: 6 }}>
          Фічі: {(current.data.features || []).join(', ') || '—'}
        </div>
      </Card>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: 12 }}>
        {entries.map(([key, p]: [string, any]) => (
          <Card key={key} style={key === current.data.plan ? { borderLeft: '4px solid var(--success)' } : undefined}>
            <b>{p.label || key}</b>
            <div className="num" style={{ fontSize: 22, fontWeight: 800 }}>{p.price_uah} ₴<span style={{ fontSize: 12 }}>/місце</span></div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Місць: {p.seats} · {(p.features || []).join(', ')}</div>
            <div style={{ marginTop: 10 }}>
              {key === current.data.plan
                ? <span style={{ fontSize: 13, color: 'var(--success)' }}>Ваш тариф</span>
                : <Button variant="ghost" onClick={() => upgrade(key)}>Перейти</Button>}
            </div>
          </Card>
        ))}
      </div>
      {entries.length === 0 && <Card><EmptyState title="Тарифів немає" /></Card>}
      {msg && <Card style={{ padding: 12 }}>{msg}</Card>}
      {upgradeRes?.pay && (
        <Card style={{ padding: 12, borderLeft: '4px solid var(--success)' }}>
          {upgradeRes.pay.signature ? (
            <form action="https://www.liqpay.ua/api/3/checkout" method="POST" acceptCharset="utf-8">
              <input type="hidden" name="data" value={upgradeRes.pay.data} />
              <input type="hidden" name="signature" value={upgradeRes.pay.signature} />
              <Button>Сплатити {upgradeRes.amount_uah} ₴ через LiqPay</Button>
            </form>
          ) : upgradeRes.pay.pageUrl ? (
            <a href={upgradeRes.pay.pageUrl} target="_blank" rel="noreferrer"
              style={{ color: 'var(--link)' }}>
              Сплатити {upgradeRes.amount_uah} ₴ через Monobank
            </a>
          ) : (
            <span>Рахунок створено, деталі оплати — у підтримки.</span>
          )}
        </Card>
      )}
      <Card>
        <h3>Рахунки</h3>
        {bills.isLoading && <Skeleton rows={2} />}
        {bills.error && <ErrorState onRetry={() => bills.refetch()} />}
        {(bills.data || []).length === 0 && !bills.isLoading && !bills.error && (
          <EmptyState title="Рахунків поки немає" />)}
        {(bills.data || []).slice(0, 10).map((b: any, i: number) => (
          <div key={b.id || i} style={{ display: 'flex', gap: 8, fontSize: 13, padding: '6px 0',
            borderTop: i ? '1px solid var(--border)' : 'none' }}>
            <Badge tone={b.status === 'paid' ? 'ok' : 'warn'}>{b.status}</Badge>
            <span>{b.plan} · {b.provider}</span>
            <b className="num" style={{ marginLeft: 'auto' }}>
              {Math.round(b.amount_uah || 0).toLocaleString('uk-UA')} ₴</b>
          </div>
        ))}
      </Card>
      <Card>
        <h3 style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <UserPlus size={18} aria-hidden /> Команда
        </h3>
        <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>
          Запросіть колегу (тільки owner/admin). Колега увійде з тимчасовим паролем і змінить його.
        </p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'end' }}>
          <label style={{ fontSize: 12, color: 'var(--text-muted)' }}>Email
            <Input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="kolega@shop.ua" aria-label="Email колеги" />
          </label>
          <label style={{ fontSize: 12, color: 'var(--text-muted)' }}>Імʼя
            <Input value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Олена" aria-label="Імʼя колеги" />
          </label>
          <label style={{ fontSize: 12, color: 'var(--text-muted)' }}>Роль
            <Select value={role} onChange={(e) => setRole(e.target.value)} aria-label="Роль">
              <option value="manager">Менеджер</option>
              <option value="viewer">Спостерігач</option>
            </Select>
          </label>
          <Button onClick={invite} disabled={!email.trim()}>Запросити</Button>
        </div>
        {inviteRes && <p>{inviteRes}</p>}
      </Card>
    </div>
  );
}
