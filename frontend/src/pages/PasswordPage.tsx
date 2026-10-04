import { useState } from 'react';
import { api } from '../api';
import { Button, Card, ErrorState, Input, Skeleton } from '../components/ui';
import { useQuery } from '@tanstack/react-query';

export default function PasswordPage() {
  const me = useQuery({ queryKey: ['me'], queryFn: () => api<any>('/auth/me') });
  const [oldP, setOldP] = useState('');
  const [newP, setNewP] = useState('');
  const [msg, setMsg] = useState('');
  const [uri, setUri] = useState('');
  const [code, setCode] = useState('');
  const [tfaMsg, setTfaMsg] = useState('');

  async function change() {
    setMsg('');
    try {
      await api('/auth/change-password', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ old_password: oldP, new_password: newP }),
      });
      setMsg('Пароль змінено. Старі сесії відкликано.');
      setOldP(''); setNewP('');
      me.refetch();
    } catch {
      setMsg('Не вдалося змінити пароль (мінімум 10 символів).');
    }
  }
  async function setup2fa() {
    setTfaMsg('');
    try {
      const r = await api<{ otpauth_uri: string }>('/auth/2fa/setup', { method: 'POST' });
      setUri(r?.otpauth_uri || '');
    } catch {
      setTfaMsg('2FA доступне власнику/адміну. Спробуйте ще раз.');
    }
  }
  async function enable2fa() {
    setTfaMsg('');
    try {
      await api('/auth/2fa/enable', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
      });
      setTfaMsg('2FA увімкнено.');
      setUri(''); setCode('');
    } catch {
      setTfaMsg('Невірний код. Перевірте час на телефоні.');
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxWidth: 560 }}>
      {me.data?.must_change_password && (
        <Card style={{ borderLeft: '4px solid var(--warning)' }}>
          <b>Потрібно змінити тимчасовий пароль</b> — без цього далі не пустить.
        </Card>
      )}
      <Card>
        <h3>Зміна пароля</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <Input type="password" value={oldP} onChange={(e) => setOldP(e.target.value)}
            placeholder="Старий пароль" aria-label="Старий пароль" />
          <Input type="password" value={newP} onChange={(e) => setNewP(e.target.value)}
            placeholder="Новий пароль (мін. 10 символів)" aria-label="Новий пароль" />
          <div><Button onClick={change} disabled={!oldP || !newP}>Змінити</Button></div>
          {msg && <span>{msg}</span>}
        </div>
      </Card>
      <Card>
        <h3>Двофакторка (TOTP)</h3>
        {me.isLoading && <Skeleton rows={2} />}
        {me.error && <ErrorState onRetry={() => me.refetch()} />}
        <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
          Для власника/адміна. Відскануйте QR в аутентифікаторі, введіть код.
        </p>
        <div><Button variant="ghost" onClick={setup2fa}>Отримати QR</Button></div>
        {uri && (
          <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <code style={{ wordBreak: 'break-all', fontSize: 12 }}>{uri}</code>
            <Input value={code} onChange={(e) => setCode(e.target.value)}
              placeholder="Код з аутентифікатора" inputMode="numeric" aria-label="Код 2FA" />
            <div><Button onClick={enable2fa} disabled={!code}>Увімкнути</Button></div>
          </div>
        )}
        {tfaMsg && <p>{tfaMsg}</p>}
      </Card>
    </div>
  );
}
