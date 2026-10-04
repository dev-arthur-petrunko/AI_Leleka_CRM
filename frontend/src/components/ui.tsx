import React from 'react';
import { Bird } from 'lucide-react';

type P = React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'ghost' | 'danger' };

export function Button({ variant = 'primary', style, className, ...rest }: P) {
  const base: React.CSSProperties = {
    padding: '10px 18px', borderRadius: 'var(--r-md)', fontWeight: 700, fontSize: 14,
    cursor: 'pointer', border: '1px solid transparent', minHeight: 40,
  };
  const v: React.CSSProperties =
    variant === 'primary'
      ? { background: 'var(--primary)', color: 'var(--primary-fg)' }
      : variant === 'danger'
        ? { background: 'var(--danger)', color: 'var(--primary-fg)' }
        : { background: 'transparent', color: 'var(--link)', borderColor: 'var(--border)' };
  return <button className={['press', className].filter(Boolean).join(' ')}
    style={{ ...base, ...v, ...style }} {...rest} />;
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      style={{
        width: '100%', padding: '10px 12px', borderRadius: 'var(--r-sm)',
        border: '1px solid var(--border)', background: 'var(--bg)', color: 'var(--text)',
        fontSize: 14, ...props.style,
      }}
    />
  );
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      style={{
        padding: '10px 12px', borderRadius: 'var(--r-sm)', border: '1px solid var(--border)',
        background: 'var(--bg)', color: 'var(--text)', fontSize: 14, ...props.style,
      }}
    />
  );
}

export function Checkbox(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input type="checkbox" {...props}
      style={{ width: 20, height: 20, accentColor: 'var(--primary)', ...props.style }} />
  );
}

export function Badge({ tone = 'info', children }: { tone?: 'info' | 'ok' | 'warn' | 'bad'; children: React.ReactNode }) {
  const map = { info: 'var(--info)', ok: 'var(--success)', warn: 'var(--warning)', bad: 'var(--danger)' };
  return (
    <span style={{ fontSize: 12, fontWeight: 700, padding: '2px 10px', borderRadius: 20,
      background: map[tone] + '22', color: map[tone] }}>{children}</span>
  );
}

export function Card({ children, style, ...rest }: {
  children: React.ReactNode; style?: React.CSSProperties;
} & React.HTMLAttributes<HTMLDivElement>) {
  return <div className="glass" style={{ padding: 18, ...style }} {...rest}>{children}</div>;
}

export function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div aria-busy="true" aria-label="Завантаження">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton-shimmer" style={{ height: 18, borderRadius: 8, background: 'var(--border)',
          opacity: 0.5, marginBottom: 8 }} />
      ))}
    </div>
  );
}

export function EmptyState({ title, hint, action }: { title: string; hint?: string; action?: React.ReactNode }) {
  return (
    <div style={{ textAlign: 'center', padding: 28, color: 'var(--text-muted)' }}>
      <Bird size={30} aria-hidden className="sway" style={{ color: 'var(--text-muted)', opacity: 0.7 }} />
      <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)', marginTop: 6 }}>{title}</div>
      {hint && <div style={{ fontSize: 13, marginTop: 4 }}>{hint}</div>}
      {action && <div style={{ marginTop: 12 }}>{action}</div>}
    </div>
  );
}

export function ErrorState({ onRetry }: { onRetry?: () => void }) {
  return (
    <div style={{ textAlign: 'center', padding: 28 }}>
      <div style={{ fontWeight: 700 }}>Не вдалося завантажити</div>
      {onRetry && <div style={{ marginTop: 12 }}><Button variant="ghost" onClick={onRetry}>Повторити</Button></div>}
    </div>
  );
}

export function Tabs({ tabs, value, onChange }: { tabs: string[]; value: string; onChange: (v: string) => void }) {
  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 12 }} role="tablist">
      {tabs.map((t) => (
        <button key={t} role="tab" aria-selected={value === t} onClick={() => onChange(t)}
          style={{ padding: '8px 14px', borderRadius: 20, border: '1px solid var(--border)',
            background: value === t ? 'var(--primary)' : 'transparent',
            color: value === t ? 'var(--primary-fg)' : 'var(--text-muted)',
            fontWeight: 600, cursor: 'pointer' }}>{t}</button>
      ))}
    </div>
  );
}
