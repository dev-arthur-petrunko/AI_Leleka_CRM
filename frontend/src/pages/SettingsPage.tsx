import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import { Button, Card, ErrorState, Skeleton } from '../components/ui';
import { applyTheme, resolveTheme, saveMode, ThemeMode } from '../theme';

const MODES: ThemeMode[] = ['auto-time', 'morning', 'evening', 'system', 'telegram'];
const MODE_LABEL: Record<ThemeMode, string> = {
  'auto-time': 'Авто (за часом)', morning: 'Ранок', evening: 'Вечір',
  system: 'Як у системі', telegram: 'Як у Telegram',
};

export default function SettingsPage() {
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
                try { localStorage.setItem('leleka.animations', v); } catch { /* ignore */ }
                await api('/auth/me/preferences', { method: 'PATCH',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ preferences: { animations: v } }) });
              }}>
              {label}
            </Button>
          ))}
        </div>
      </Card>
      <Card>
        <h3>Команда</h3>
        {me.isLoading && <Skeleton rows={2} />}
        {me.error && <ErrorState onRetry={() => me.refetch()} />}
        {me.data && <p>Ви: <b>{me.data.email}</b> ({me.data.role})</p>}
        <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
          Запрошення, воронки, шаблони і тарифи — через API (POST /auth/invite, /views, /billing).
        </p>
      </Card>
    </div>
  );
}
