import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { History, Mail, Send, X } from 'lucide-react';
import { api } from '../api';
import { Badge, Button, Card, ErrorState, Input, Select, Skeleton } from './ui';
import { t } from '../i18n';

type Client = { id: string; name: string; phone?: string; segment?: string; temperature?: string | null };

function segmentTone(s?: string): 'info' | 'ok' | 'warn' | 'bad' {
  if (s === 'vip') return 'ok';
  if (s === 'regular') return 'info';
  if (s === 'lost') return 'bad';
  return 'warn';
}

function TempBadge({ temp }: { temp?: string | null }) {
  if (!temp) return null;
  const tone = temp === 'hot' ? 'bad' : temp === 'warm' ? 'warn' : 'info';
  return (
    <Badge tone={tone as 'bad'}>
      {t('score.' + temp)} · {t('temp.manual')}
    </Badge>
  );
}

export default function ClientDrawer({ client, onClose }: { client: Client; onClose: () => void }) {
  const qc = useQueryClient();
  const [channel, setChannel] = useState('telegram');
  const [subject, setSubject] = useState('');
  const [preview, setPreview] = useState<any>(null);
  const [previewing, setPreviewing] = useState(false);
  const [msg, setMsg] = useState('');
  const [confirmDel, setConfirmDel] = useState(false);
  const [confirmErase, setConfirmErase] = useState(false);
  const [seg, setSeg] = useState(client.segment || 'new');
  const [temp, setTemp] = useState(client.temperature || '');
  const me = useQuery({ queryKey: ['me'], queryFn: () => api<{ role: string }>('/auth/me') });
  const canErase = me.data?.role === 'owner' || me.data?.role === 'admin';
  const hist = useQuery({
    queryKey: ['interactions', client.id],
    queryFn: () => api<any[]>(`/clients/${client.id}/interactions?limit=50`),
  });

  async function doPreview() {
    setMsg(''); setPreview(null);
    setPreviewing(true);
    try {
      const r = await api<any>(`/clients/${client.id}/message-preview?channel=${channel}`);
      setPreview(r);
    } catch {
      setMsg('Не вдалося згенерувати перегляд.');
    } finally {
      setPreviewing(false);
    }
  }
  async function send() {
    setMsg('');
    try {
      const r = await api<any>(`/clients/${client.id}/message`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel, subject: subject || undefined }),
      });
      setMsg(r ? `Надіслано (${r.ai_used ? 'AI-текст' : 'шаблон'}).` : 'Надіслано.');
      setPreview(null);
      qc.invalidateQueries({ queryKey: ['interactions', client.id] });
    } catch (e: any) {
      setMsg(`Не надіслано: ${e?.message || 'помилка'}. Можливо, в клієнта немає контакту каналу.`);
    }
  }

  return (
    <div onClick={onClose}
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', zIndex: 60,
        display: 'flex', justifyContent: 'flex-end' }}>
      <div className="glass drawer-in" onClick={(e) => e.stopPropagation()}
        style={{ width: 460, maxWidth: '94vw', height: '100%', overflowY: 'auto', padding: 18 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <h2 style={{ margin: 0, flex: 1 }}>{client.name}</h2>
          <button onClick={onClose} aria-label="Закрити"
            style={{ background: 'transparent', border: '1px solid var(--border)', borderRadius: 10,
              width: 40, height: 40, display: 'inline-flex', alignItems: 'center',
              justifyContent: 'center', cursor: 'pointer', color: 'var(--text)' }}>
            <X size={18} />
          </button>
        </div>
        {client.phone && <div className="num" style={{ color: 'var(--link)', marginTop: 4 }}>{client.phone}</div>}
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 10, flexWrap: 'wrap' }}>
          <Badge tone={segmentTone(seg)}>{t('segment.' + seg)}</Badge>
          <Select value={seg} aria-label="Сегмент клієнта" onChange={async (e) => {
            const next = e.target.value;
            const prev = seg;
            setSeg(next);
            try {
              await api(`/clients/${client.id}`, {
                method: 'PATCH', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ segment: next }),
              });
              qc.invalidateQueries({ queryKey: ['clients'] });
            } catch {
              setSeg(prev);
              setMsg('Не вдалося змінити сегмент.');
            }
          }}>
            {['new', 'regular', 'vip', 'lost'].map((s) => (
              <option key={s} value={s}>{t('segment.' + s)}</option>))}
          </Select>
          <TempBadge temp={temp} />
          <Select value={temp} aria-label="Температура клієнта" onChange={async (e) => {
            const next = e.target.value;
            const prev = temp;
            setTemp(next);
            try {
              await api(`/clients/${client.id}`, {
                method: 'PATCH', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ temperature: next }),
              });
              qc.invalidateQueries({ queryKey: ['clients'] });
            } catch {
              setTemp(prev);
              setMsg('Не вдалося змінити температуру.');
            }
          }}>
            <option value="">{t('temp.auto')}</option>
            {(['hot', 'warm', 'cold'] as const).map((s) => (
              <option key={s} value={s}>{t('score.' + s)}</option>))}
          </Select>
        </div>
        <div style={{ marginTop: 8 }}>
          {!confirmDel ? (
            <Button variant="ghost" onClick={() => setConfirmDel(true)}>Видалити клієнта</Button>
          ) : (
            <span style={{ display: 'inline-flex', gap: 8, alignItems: 'center', fontSize: 13 }}>
              Точно видалити?
              <Button variant="ghost" onClick={async () => {
                try {
                  await api(`/clients/${client.id}`, { method: 'DELETE' });
                  qc.invalidateQueries({ queryKey: ['clients'] });
                  onClose();
                } catch {
                  setMsg('Не вдалося видалити.');
                  setConfirmDel(false);
                }
              }}>Так</Button>
              <Button variant="ghost" onClick={() => setConfirmDel(false)}>Ні</Button>
            </span>
          )}
        </div>
        {canErase && (
          <div style={{ marginTop: 8 }}>
            {!confirmErase ? (
              <Button variant="ghost" onClick={() => setConfirmErase(true)}>
                Стерти персональні дані (GDPR)
              </Button>
            ) : (
              <span style={{ display: 'inline-flex', gap: 8, alignItems: 'center', fontSize: 13 }}>
                Імʼя/телефон буде знеособлено. Продовжити?
                <Button onClick={async () => {
                  try {
                    await api(`/clients/${client.id}/erase`, { method: 'DELETE' });
                    qc.invalidateQueries({ queryKey: ['clients'] });
                    onClose();
                  } catch {
                    setMsg('Не вдалося стерти.');
                    setConfirmErase(false);
                  }
                }}>Так</Button>
                <Button variant="ghost" onClick={() => setConfirmErase(false)}>Ні</Button>
              </span>
            )}
          </div>
        )}

        <section style={{ marginTop: 14 }}>
          <h4 style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <Mail size={15} aria-hidden /> Написати клієнту
          </h4>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'end' }}>
            <label style={{ fontSize: 12, color: 'var(--text-muted)' }}>Канал
              <Select value={channel} onChange={(e) => setChannel(e.target.value)} aria-label="Канал">
                {['telegram', 'viber', 'email'].map((c) => (
                  <option key={c} value={c}>{t('ch.' + c)}</option>))}
              </Select>
            </label>
            {channel === 'email' && (
              <label style={{ fontSize: 12, color: 'var(--text-muted)' }}>Тема
                <Input value={subject} onChange={(e) => setSubject(e.target.value)} aria-label="Тема листа" />
              </label>
            )}
            <Button variant="ghost" onClick={doPreview}>Перегляд</Button>
            <Button onClick={send}><Send size={14} /> Надіслати</Button>
          </div>
          <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            Текст складає сервер (AI або шаблон). Шаблони — у «Вхідні» та автоматизаціях.
          </p>
          {previewing && (
            <div role="status" aria-label="AI думає" className="typing" style={{ marginTop: 8 }}>
              <span /><span /><span />
            </div>
          )}
          {preview && (
            <Card style={{ marginTop: 8, padding: 12, background: 'var(--bg-hover)' }}>
              {(String(preview.text || '').split('\n')).map((line: string, i: number) => (
                <div key={i} className="line-in" style={{ animationDelay: `${i * 120}ms` }}>
                  {line || ' '}
                </div>
              ))}
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6 }}>
                {preview.ai_used ? 'AI-текст (без персональних даних у запиті).' : 'Локальний шаблон.'}
                {!preview.can_send && preview.send_hint ? ` ${preview.send_hint}` : ''}
              </div>
            </Card>
          )}
          {msg && <p>{msg}</p>}
        </section>

        <section style={{ marginTop: 14 }}>
          <h4 style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <History size={15} aria-hidden /> Історія спілкування
          </h4>
          {hist.isLoading && <Skeleton rows={4} />}
          {hist.error && <ErrorState onRetry={() => hist.refetch()} />}
          {(hist.data || []).length === 0 && !hist.isLoading && !hist.error && (
            <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>Поки порожньо.</p>
          )}
          {(hist.data || []).map((h: any, i: number) => (
            <div key={h.id || i} style={{ fontSize: 13, padding: '7px 0',
              borderTop: i ? '1px solid var(--border)' : 'none' }}>
              <Badge>{h.channel}</Badge>{' '}
              <span style={{ color: 'var(--text-muted)' }}>{h.created_at || ''}</span>
              <div style={{ marginTop: 2 }}>{h.body}</div>
            </div>
          ))}
        </section>
      </div>
    </div>
  );
}
