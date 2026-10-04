import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, PlugZap, Plus, RefreshCw, X, XCircle } from 'lucide-react';
import { api } from '../api';
import { Button, Card, EmptyState, ErrorState, Input, Select, Skeleton } from '../components/ui';

type Integ = { provider: string; is_active: boolean; has_key: boolean; status: string;
  last_error?: string; last_sync_at?: string };

export default function IntegrationsPage() {
  const qc = useQueryClient();
  const [msg, setMsg] = useState('');
  const [wiz, setWiz] = useState(false);
  const { data, error, isLoading, refetch } = useQuery({
    queryKey: ['integrations'], queryFn: () => api<Integ[]>('/integrations'),
  });
  async function syncNow(provider: string) {
    setMsg('');
    try {
      await api(`/integrations/${provider}/import-orders`, { method: 'POST' });
      qc.invalidateQueries({ queryKey: ['integrations'] });
    } catch {
      setMsg('Не вдалося запустити синхронізацію. Спробуйте ще раз.');
    }
  }
  async function testNow(provider: string) {
    setMsg('Перевірка…');
    try {
      const r = await api<{ ok: boolean; detail?: string }>(
        `/integrations/${provider}/test`, { method: 'POST' });
      setMsg(r && r.ok ? 'Перевірка пройшла: ключ робочий.' : `Помилка: ${r?.detail || 'ключ не працює'}`);
      qc.invalidateQueries({ queryKey: ['integrations'] });
    } catch {
      setMsg('Не вдалося перевірити. Спробуйте ще раз.');
    }
  }
  if (isLoading) return <Card><Skeleton rows={5} /></Card>;
  if (error || !data) return <Card><ErrorState onRetry={() => refetch()} /></Card>;
  return (
    <>
    <Card>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <h2 style={{ margin: 0, flex: 1 }}>Інтеграції</h2>
        <Button onClick={() => setWiz(true)}><Plus size={15} /> Підключити</Button>
      </div>
      {data.length === 0 && (
        <EmptyState title="Нічого не підключено" hint="Почніть з Prom або Rozetka — замовлення потечуть самі." />
      )}
      {data.map((r) => (
        <div key={r.provider} style={{ display: 'flex', gap: 10, alignItems: 'center',
          padding: '12px 0', borderTop: '1px solid var(--border)' }}>
          {r.status === 'ok' && r.has_key
            ? <CheckCircle2 size={20} color="var(--success)" aria-label="Підключено" />
            : <XCircle size={20} color="var(--danger)" aria-label="Помилка" />}
          <div>
            <b>{r.provider}</b>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {r.status === 'ok' && r.has_key ? 'Підключено' : r.status === 'auth_failed' ? 'Помилка: токен недійсний' : 'Не підключено'}
              {r.last_sync_at ? ` · синхронізовано ${r.last_sync_at}` : ''}
              {r.last_error ? ` · ${r.last_error}` : ''}
            </div>
          </div>
          <span style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
            <Button variant="ghost" onClick={() => syncNow(r.provider)}>
              <RefreshCw size={14} /> Синхронізувати
            </Button>
            <Button variant="ghost" onClick={() => testNow(r.provider)}>
              <PlugZap size={14} /> Тест
            </Button>
          </span>
        </div>
      ))}
      {msg && <p>{msg}</p>}
    </Card>
    {wiz && <Wizard onClose={() => { setWiz(false); refetch(); }} />}
    </>
  );
}

const SIMPLE_KEY: Record<string, string> = {
  prom: 'token', rozetka: 'token', monobank: 'token', turbosms: 'token',
  novaposhta: 'api_key', telegram: 'bot_token', viber: 'auth_token',
};
const PROVIDERS = ['prom', 'rozetka', 'novaposhta', 'telegram', 'viber', 'email',
  'checkbox', 'liqpay', 'monobank', 'sendpulse', 'turbosms'];
const JSON_HINT: Record<string, string> = {
  email: '{"smtp_user": "...", "smtp_password": "..."}',
  checkbox: '{"login": "...", "password": "..."}',
  liqpay: '{"public_key": "...", "private_key": "..."}',
  sendpulse: '{"client_id": "...", "client_secret": "..."}',
};

function Wizard({ onClose }: { onClose: () => void }) {
  const [provider, setProvider] = useState('prom');
  const [key, setKey] = useState('');
  const [json, setJson] = useState('');
  const [step, setStep] = useState('');
  const [hook, setHook] = useState<any>(null);

  async function save() {
    setStep('');
    let creds: Record<string, string> = {};
    try {
      if (SIMPLE_KEY[provider]) {
        if (!key.trim()) { setStep('Вставте ключ.'); return; }
        creds = { [SIMPLE_KEY[provider]]: key.trim() };
      } else {
        creds = JSON.parse(json || '{}');
      }
    } catch {
      setStep('Ключі — невалідний JSON.');
      return;
    }
    try {
      setStep('Збереження…');
      await api('/integrations', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, credentials: creds }),
      });
      setStep('Перевірка…');
      const r = await api<any>(`/integrations/${provider}/test`, { method: 'POST' });
      if (r && r.ok === false) {
        setStep(`Ключ збережено, але перевірка не пройшла: ${r.error || r.detail || 'помилка'}`);
        return;
      }
      const h = await api<any>(`/integrations/${provider}/webhook-url`).catch(() => null);
      setHook(h);
      setStep('Готово: ключ робочий. Вставте адресу вебхука в кабінет провайдера.');
    } catch (e: any) {
      setStep(`Помилка: ${e?.message || 'спробуйте ще раз'}. Можливо, потрібен інший тариф (402).`);
    }
  }
  return (
    <div onClick={onClose}
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', zIndex: 60,
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <div className="glass" onClick={(e) => e.stopPropagation()}
        style={{ padding: 22, maxWidth: 440, width: '100%' }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <h3 style={{ margin: 0, flex: 1 }}>Майстер підключення</h3>
          <button onClick={onClose} aria-label="Закрити"
            style={{ background: 'transparent', border: '1px solid var(--border)', borderRadius: 10,
              width: 40, height: 40, display: 'inline-flex', alignItems: 'center',
              justifyContent: 'center', cursor: 'pointer', color: 'var(--text)' }}>
            <X size={18} />
          </button>
        </div>
        <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>Крок 1 — провайдер і ключ →
          крок 2 — перевірка → крок 3 — адреса вебхука.</p>
        <label style={{ fontSize: 12, color: 'var(--text-muted)' }}>Провайдер
          <Select value={provider} onChange={(e) => { setProvider(e.target.value); setStep(''); setHook(null); }}
            aria-label="Провайдер" style={{ width: '100%' }}>
            {PROVIDERS.map((p) => <option key={p} value={p}>{p}</option>)}
          </Select>
        </label>
        {SIMPLE_KEY[provider] ? (
          <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginTop: 8 }}>Ключ
            <Input value={key} onChange={(e) => setKey(e.target.value)} type="password"
              placeholder={`${SIMPLE_KEY[provider]}`} aria-label="Ключ" style={{ marginTop: 4 }} />
          </label>
        ) : (
          <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginTop: 8 }}>Ключі (JSON)
            <Input value={json} onChange={(e) => setJson(e.target.value)}
              placeholder={JSON_HINT[provider] || '{"token": "..."}'} aria-label="Ключі JSON" style={{ marginTop: 4 }} />
          </label>
        )}
        {step && <p>{step}</p>}
        {hook && (
          <Card style={{ marginTop: 8, padding: 12, background: 'var(--bg-hover)' }}>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Адреса вебхука:</div>
            <code className="num" style={{ wordBreak: 'break-all', fontSize: 12 }}>{hook.webhook_url}</code>
            {hook.secret && (
              <div style={{ fontSize: 12, marginTop: 6 }}>Секрет: <code>{hook.secret}</code>
                <div style={{ color: 'var(--text-muted)' }}>{hook.usage}</div></div>)}
          </Card>
        )}
        <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
          <Button onClick={save}>Зберегти і перевірити</Button>
          <Button variant="ghost" onClick={onClose}>Готово</Button>
        </div>
      </div>
    </div>
  );
}
