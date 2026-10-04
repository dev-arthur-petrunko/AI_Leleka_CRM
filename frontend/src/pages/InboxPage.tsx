import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Send } from 'lucide-react';
import { api } from '../api';
import { Badge, Button, Card, EmptyState, ErrorState, Skeleton } from '../components/ui';
import { t } from '../i18n';

type Conv = { id: string; channel: string; status: string; last_message_at?: string };
type Msg = { id: string; direction: string; body: string };

export default function InboxPage() {
  const [cur, setCur] = useState<string | null>(null);
  const [text, setText] = useState('');
  const qc = useQueryClient();
  const convs = useQuery({
    queryKey: ['convs'], queryFn: () => api<Conv[]>('/inbox/conversations?limit=30'),
  });
  const thread = useQuery({
    queryKey: ['thread', cur], enabled: !!cur,
    queryFn: () => api<{ conversation: Conv; messages: Msg[] }>(`/inbox/conversations/${cur}`),
  });
  async function send() {
    if (!cur || !text.trim()) return;
    try {
      await api(`/inbox/conversations/${cur}/reply`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ body: text }),
      });
      setText('');
      thread.refetch();
    } catch { /* помилка відправки — текст лишається в полі, видно при повторі */ }
  }
  if (convs.isLoading) return <Card><Skeleton rows={5} /></Card>;
  if (convs.error || !convs.data) return <Card><ErrorState onRetry={() => convs.refetch()} /></Card>;
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.4fr', gap: 12 }}>
      <Card>
        <h3>Діалоги</h3>
        {convs.data.length === 0 && (
          <EmptyState title="Порожньо" hint="Діалоги зʼявляться, коли клієнти напишуть боту."
            action={<a href="/integrations">Підключити Telegram</a>} />
        )}
        {convs.data.map((c) => (
          <div key={c.id} onClick={() => setCur(c.id)}
            style={{ padding: '10px 0', borderTop: '1px solid var(--border)', cursor: 'pointer',
              fontWeight: cur === c.id ? 700 : 400 }}>
            {t('ch.' + c.channel)} · <Badge tone={c.status === 'open' ? 'info' : 'warn'}>
              {t('conv.' + c.status)}</Badge>
          </div>
        ))}
      </Card>
      <Card>
        {!cur && <EmptyState title="Оберіть діалог" />}
        {cur && thread.data?.conversation && (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
            <b>{t('ch.' + thread.data.conversation.channel)}</b>
            <Badge tone={thread.data.conversation.status === 'open' ? 'info' : 'warn'}>
              {t('conv.' + thread.data.conversation.status)}
            </Badge>
            <span style={{ flex: 1 }} />
            <Button variant="ghost" onClick={async () => {
              const conv = thread.data?.conversation;
              if (!conv) return;
              try {
                await api(`/inbox/conversations/${cur}`, {
                  method: 'PATCH', headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ status: conv.status === 'open' ? 'closed' : 'open' }),
                });
                qc.invalidateQueries({ queryKey: ['convs'] });
                thread.refetch();
              } catch { /* ignore */ }
            }}>
              {thread.data.conversation.status === 'open' ? 'Закрити діалог' : 'Відкрити знову'}
            </Button>
          </div>
        )}
        {thread.data?.messages.map((m) => (
          <div key={m.id} style={{ padding: 8, marginBottom: 6, borderRadius: 10,
            background: m.direction === 'out' ? 'var(--bg-hover)' : 'transparent',
            border: '1px solid var(--border)', textAlign: m.direction === 'out' ? 'right' : 'left' }}>
            {m.body}
          </div>
        ))}
        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Відповідь…"
            disabled={!cur} style={{ flex: 1, padding: 10, borderRadius: 8 }} aria-label="Відповідь" />
          <button onClick={send} disabled={!cur} aria-label="Надіслати"><Send size={16} /></button>
        </div>
      </Card>
    </div>
  );
}
