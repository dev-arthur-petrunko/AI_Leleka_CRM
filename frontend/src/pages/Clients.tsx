import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Copy, Phone, Search, User } from 'lucide-react';
import { api } from '../api';
import { Badge, Button, Card, EmptyState, ErrorState, Input, Select, Skeleton } from '../components/ui';
import ClientDrawer from '../components/ClientDrawer';
import { t } from '../i18n';

type Client = { id: string; name: string; phone?: string; segment: string };

function fmtPhone(p?: string): string {
  if (!p) return '';
  const d = p.replace(/\D/g, '');
  const m = d.match(/^380(\d{2})(\d{3})(\d{2})(\d{2})$/);
  return m ? `+380 ${m[1]} ${m[2]} ${m[3]} ${m[4]}` : p;
}

function segmentTone(s: string): 'info' | 'ok' | 'warn' | 'bad' {
  if (s === 'vip') return 'ok';
  if (s === 'regular') return 'info';
  if (s === 'lost') return 'bad';
  return 'warn';
}

function initial(name: string): string {
  return (name.trim()[0] || '?').toUpperCase();
}

export default function Clients() {
  const [q, setQ] = useState('');
  const [seg, setSeg] = useState('');
  const [open, setOpen] = useState<Client | null>(null);
  const { data, error, isLoading, refetch } = useQuery({
    queryKey: ['clients', q, seg],
    queryFn: () => api<{ total: number; items: Client[] }>(
      `/clients?limit=50${q ? `&q=${encodeURIComponent(q)}` : ''}${seg ? `&segment=${seg}` : ''}`),
  });
  if (isLoading) return <Card><Skeleton rows={6} /></Card>;
  if (error || !data) return <Card><ErrorState onRetry={() => refetch()} /></Card>;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <Card style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: '1 1 220px' }}>
          <Search size={16} aria-hidden
            style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Пошук за імʼям або телефоном…"
            aria-label="Пошук клієнтів" style={{ paddingLeft: 34 }} />
        </div>
        <Select value={seg} onChange={(e) => setSeg(e.target.value)} aria-label="Сегмент" style={{ minWidth: 150 }}>
          <option value="">Всі сегменти</option>
          {['new', 'regular', 'vip', 'lost'].map((s) => <option key={s} value={s}>{t('segment.' + s)}</option>)}
        </Select>
        <span className="num" style={{ color: 'var(--text-muted)', fontSize: 13, marginLeft: 'auto' }}>
          {data.total} клієнтів
        </span>
      </Card>
      {data.items.length === 0 && (
        <Card><EmptyState title="Клієнтів не знайдено" hint="Змініть пошук або додайте першого клієнта."
          action={<Button onClick={() => { setQ(''); setSeg(''); }}>Скинути фільтри</Button>} /></Card>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(300px,1fr))', gap: 12 }}>
        {data.items.map((c) => {
          const phone = fmtPhone(c.phone);
          return (
            <Card key={c.id} style={{ padding: 14, display: 'flex', gap: 12, cursor: 'pointer' }}
              onClick={() => setOpen(c)} role="button" tabIndex={0}
              onKeyDown={(e) => { if (e.key === 'Enter') setOpen(c); }}
              aria-label={`Клієнт ${c.name}`}>
              <span aria-hidden
                style={{ width: 46, height: 46, borderRadius: '50%', flex: 'none',
                  background: 'var(--bg-hover)', color: 'var(--text)',
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  fontWeight: 800, fontSize: 18 }}>
                {initial(c.name)}
              </span>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', minWidth: 0 }}>
                  <User size={15} aria-hidden style={{ color: 'var(--text-muted)', flex: 'none' }} />
                  <b style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.name}</b>
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 8, minWidth: 0 }}>
                  <Phone size={15} aria-hidden style={{ color: 'var(--text-muted)', flex: 'none' }} />
                  {phone ? (
                    <>
                      <a href={`tel:${c.phone?.replace(/\D/g, '') ? `+${c.phone.replace(/\D/g, '')}` : ''}`}
                        onClick={(e) => e.stopPropagation()}
                        className="num"
                        style={{ color: 'var(--link)', textDecoration: 'none', fontSize: 14 }}>
                        {phone}
                      </a>
                      <button aria-label={`Скопіювати телефон ${phone}`}
                        title="Скопіювати"
                        onClick={(e) => { e.stopPropagation(); if (phone) navigator.clipboard?.writeText(phone).catch(() => {}); }}
                        style={{ background: 'transparent', border: '1px solid var(--border)',
                          borderRadius: 8, width: 32, height: 32, minHeight: 32,
                          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                          color: 'var(--text-muted)', cursor: 'pointer' }}>
                        <Copy size={14} />
                      </button>
                    </>
                  ) : (
                    <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>Без телефону</span>
                  )}
                </div>
                <div style={{ marginTop: 10 }}>
                  <Badge tone={segmentTone(c.segment)}>{t('segment.' + c.segment)}</Badge>
                </div>
              </div>
            </Card>
          );
        })}
      </div>
      {open && <ClientDrawer client={open} onClose={() => setOpen(null)} />}
    </div>
  );
}
