import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import { Badge, Button, Card, EmptyState, ErrorState, Input, Select, Skeleton } from '../components/ui';
import { applyAnim, applyTheme, resolveTheme, saveMode, ThemeMode } from '../theme';

const MODES: ThemeMode[] = ['auto-time', 'morning', 'evening', 'system', 'telegram'];
const MODE_LABEL: Record<ThemeMode, string> = {
  'auto-time': 'Авто (за часом)', morning: 'Ранок', evening: 'Вечір',
  system: 'Як у системі', telegram: 'Як у Telegram',
};

export default function SettingsPage() {
  const qc = useQueryClient();
  const [fEntity, setFEntity] = useState('client');
  const [fKey, setFKey] = useState('');
  const [fLabel, setFLabel] = useState('');
  const [fType, setFType] = useState('text');
  const [fMsg, setFMsg] = useState('');
  // сервер міг перевизначити режим (інший пристрій) — підтягуємо при вході
  useEffect(() => {
    try {
      const a = document.documentElement.dataset.anim;
      if (a === 'all' || a === 'min' || a === 'off') setAnim(a);
    } catch { /* ignore */ }
  }, []);
  const [mode, setMode] = useState<ThemeMode>(() => {
    try { return (localStorage.getItem('leleka.themeMode') as ThemeMode) || 'auto-time'; }
    catch { return 'auto-time'; }
  });
  const [anim, setAnim] = useState<string>(() => {
    try { return localStorage.getItem('leleka.animations') || 'all'; }
    catch { return 'all'; }
  });
  const me = useQuery({ queryKey: ['me'], queryFn: () => api<any>('/auth/me') });
  function pick(m: ThemeMode) {
    setMode(m);
    saveMode(m);
    applyTheme(resolveTheme(m));
  }
  return (
    <div>
      <Card style={{ marginBottom: 12 }}>
        <h3>Вигляд</h3>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {MODES.map((m) => (
            <Button key={m} variant={mode === m ? 'primary' : 'ghost'} onClick={() => pick(m)}>
              {MODE_LABEL[m]}
            </Button>
          ))}
        </div>
        <h3 style={{ marginTop: 16 }}>Анімації</h3>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {[['all', 'Усі'], ['min', 'Мінімум'], ['off', 'Вимкнено']].map(([v, label]) => (
            <Button key={v} variant={anim === v ? 'primary' : 'ghost'}
              onClick={async () => {
                setAnim(v);
                applyAnim(v as 'all' | 'min' | 'off');
                await api('/auth/me/preferences', { method: 'PATCH',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ preferences: { animations: v } }) }).catch(() => null);
              }}>
              {label}
            </Button>
          ))}
        </div>
      </Card>
      <Card style={{ marginBottom: 12 }}>
        <h3>Команда і безпека</h3>
        {me.isLoading && <Skeleton rows={2} />}
        {me.error && <ErrorState onRetry={() => me.refetch()} />}
        {me.data && <p>Ви: <b>{me.data.email}</b> ({me.data.role})</p>}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <Link to="/billing"><Button variant="ghost">Команда і тариф</Button></Link>
          <Link to="/password"><Button variant="ghost">Пароль і 2FA</Button></Link>
        </div>
      </Card>
      <PipelinesCard />
      <CustomFieldsCard qc={qc} fEntity={fEntity} setFEntity={setFEntity} fKey={fKey} setFKey={setFKey}
        fLabel={fLabel} setFLabel={setFLabel} fType={fType} setFType={setFType} fMsg={fMsg} setFMsg={setFMsg} />
      <TagsCard />
      <AuditCard />
    </div>
  );
}

function PipelinesCard() {
  const q = useQuery({ queryKey: ['pipelines'], queryFn: () => api<any[]>('/orders/pipelines') });
  return (
    <Card style={{ marginBottom: 12 }}>
      <h3>Воронки</h3>
      {q.isLoading && <Skeleton rows={3} />}
      {q.error && <ErrorState onRetry={() => q.refetch()} />}
      {(q.data || []).map((p: any, i: number) => (
        <div key={i} style={{ marginBottom: 8 }}>
          <b>{p.pipeline?.name || 'Воронка'}</b>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
            {(p.stages || []).map((s: any, j: number) => (
              <Badge key={j}>{s.name || s.key}</Badge>))}
          </div>
        </div>
      ))}
    </Card>
  );
}

function CustomFieldsCard(props: {
  qc: any; fEntity: string; setFEntity: (v: string) => void; fKey: string; setFKey: (v: string) => void;
  fLabel: string; setFLabel: (v: string) => void; fType: string; setFType: (v: string) => void;
  fMsg: string; setFMsg: (v: string) => void;
}) {
  const { qc } = props;
  const q = useQuery({ queryKey: ['custom-fields'], queryFn: () => api<any[]>('/orders/custom-fields') });
  async function add() {
    props.setFMsg('');
    if (!props.fKey.trim() || !props.fLabel.trim()) return;
    try {
      await api('/orders/custom-fields', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entity: props.fEntity, key: props.fKey.trim(),
          label: props.fLabel.trim(), ftype: props.fType }),
      });
      props.setFKey(''); props.setFLabel('');
      qc.invalidateQueries({ queryKey: ['custom-fields'] });
    } catch {
      props.setFMsg('Не вдалося створити поле.');
    }
  }
  return (
    <Card style={{ marginBottom: 12 }}>
      <h3>Свої поля</h3>
      {q.isLoading && <Skeleton rows={2} />}
      {q.error && <ErrorState onRetry={() => q.refetch()} />}
      {(q.data || []).length === 0 && !q.isLoading && !q.error && (
        <EmptyState title="Полів поки немає" hint="Наприклад: «Розмір» для замовлень." />)}
      {(q.data || []).map((f: any, i: number) => (
        <div key={f.id || i} style={{ fontSize: 13, padding: '5px 0' }}>
          <Badge>{f.entity}</Badge> <b>{f.label}</b>{' '}
          <span style={{ color: 'var(--text-muted)' }}>{f.key} · {f.ftype}</span>
        </div>
      ))}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'end', marginTop: 8 }}>
        <label style={{ fontSize: 12, color: 'var(--text-muted)' }}>Сутність
          <Select value={props.fEntity} onChange={(e) => props.setFEntity(e.target.value)} aria-label="Сутність">
            <option value="client">Клієнт</option>
            <option value="order">Замовлення</option>
          </Select>
        </label>
        <label style={{ fontSize: 12, color: 'var(--text-muted)' }}>Ключ
          <Input value={props.fKey} onChange={(e) => props.setFKey(e.target.value)} placeholder="size" aria-label="Ключ поля" />
        </label>
        <label style={{ fontSize: 12, color: 'var(--text-muted)' }}>Підпис
          <Input value={props.fLabel} onChange={(e) => props.setFLabel(e.target.value)} placeholder="Розмір" aria-label="Підпис поля" />
        </label>
        <label style={{ fontSize: 12, color: 'var(--text-muted)' }}>Тип
          <Select value={props.fType} onChange={(e) => props.setFType(e.target.value)} aria-label="Тип поля">
            {['text', 'number', 'date', 'bool'].map((x) => <option key={x} value={x}>{x}</option>)}
          </Select>
        </label>
        <Button onClick={add}>Додати</Button>
      </div>
      {props.fMsg && <p>{props.fMsg}</p>}
    </Card>
  );
}

function TagsCard() {
  const q = useQuery({ queryKey: ['tags'], queryFn: () => api<any[]>('/orders/tags/all') });
  return (
    <Card style={{ marginBottom: 12 }}>
      <h3>Теги</h3>
      {q.isLoading && <Skeleton rows={2} />}
      {q.error && <ErrorState onRetry={() => q.refetch()} />}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {(q.data || []).map((x: any, i: number) => <Badge key={x.id || i}>{x.name}</Badge>)}
      </div>
      {(q.data || []).length === 0 && !q.isLoading && !q.error && (
        <EmptyState title="Тегів поки немає" hint="Теги створюються при прикріпленні до клієнта чи замовлення." />)}
    </Card>
  );
}

function AuditCard() {
  const q = useQuery({ queryKey: ['audit'], queryFn: () => api<any[]>('/audit?limit=50') });
  return (
    <Card>
      <h3>Журнал змін</h3>
      {q.isLoading && <Skeleton rows={3} />}
      {q.error && <ErrorState onRetry={() => q.refetch()} />}
      {(q.data || []).length === 0 && !q.isLoading && !q.error && (
        <EmptyState title="Поки порожньо" hint="Зміни клієнтів і тарифу зʼявляться тут." />)}
      {(q.data || []).slice(0, 20).map((a: any, i: number) => (
        <div key={i} style={{ fontSize: 13, padding: '5px 0', borderTop: i ? '1px solid var(--border)' : 'none' }}>
          <b>{a.action}</b> · {a.entity_type}
          {a.actor && <span style={{ color: 'var(--text-muted)' }}> · {a.actor}</span>}
          <span style={{ color: 'var(--text-muted)' }}> · {a.created_at || ''}</span>
        </div>
      ))}
    </Card>
  );
}
