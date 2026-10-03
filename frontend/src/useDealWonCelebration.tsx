import { useCallback, useRef, useState } from 'react';
import logoMark from '../assets/brand/logo-mark.png';

export type AnimMode = 'all' | 'min' | 'off';

type CelebrateArgs = {
  dealId: string;
  amount: number;
  anchorEl?: HTMLElement | null;
  onCreateOrder: () => void;
};

const RECENT = new Map<string, number>();

/** Чи можна святкувати: не частіше 1 разу на 5 с для тієї самої угоди. */
export function shouldCelebrate(dealId: string, now = Date.now()): boolean {
  const last = RECENT.get(dealId) || 0;
  if (now - last < 5000) return false;
  RECENT.set(dealId, now);
  return true;
}

export function celebrationMode(): AnimMode {
  try {
    return (localStorage.getItem('leleka.animations') as AnimMode) || 'all';
  } catch {
    return 'all';
  }
}

export function reducedMotion(): boolean {
  return matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/** Єдиний хук свята виграшу — канбан, таблиця, drawer. Повертає JSX тосту. */
export function useDealWonCelebration() {
  const [toast, setToast] = useState<null | { dealId: string; amount: number }>(null);
  const [spectacle, setSpectacle] = useState(false);
  const timer = useRef<number | null>(null);
  const onCreateOrderRef = useRef<(() => void) | null>(null);

  const celebrate = useCallback(async ({ dealId, amount, anchorEl, onCreateOrder }: CelebrateArgs) => {
    if (!shouldCelebrate(dealId)) return;
    const mode = celebrationMode();
    if (mode === 'off') return;
    onCreateOrderRef.current = onCreateOrder;
    setToast({ dealId, amount });
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => { setToast(null); setSpectacle(false); }, 8000);
    const full = mode === 'all' && !reducedMotion();
    setSpectacle(full);
    if (!full) return; // «Мінімум»: тільки підсвітка + тост
    const rect = anchorEl?.getBoundingClientRect();
    const origin = rect
      ? { x: (rect.left + rect.width / 2) / window.innerWidth, y: Math.min(0.9, rect.top / window.innerHeight) }
      : { x: 0.5, y: 0.4 };
    const big = amount >= 50000;
    const { default: confetti } = await import('canvas-confetti');
    confetti({
      particleCount: window.innerWidth < 768 ? 60 : big ? 140 : 90,
      spread: 110, origin, disableForReducedMotion: true,
      colors: ['#BD5A2A', '#2C5A5B', '#F7F2E9', '#D9A441', '#ffffff'],
    });
    if (big) {
      window.setTimeout(() => confetti({
        particleCount: 80, spread: 130, origin: { x: 0.5, y: 0.3 },
        colors: ['#BD5A2A', '#D9A441', '#ffffff'], disableForReducedMotion: true,
      }), 450);
    }
  }, []);

  const close = () => { setToast(null); setSpectacle(false); };

  const toastEl = toast ? (
    spectacle ? (
      <div role="status" aria-live="polite" onClick={close}
        style={{ position: 'fixed', inset: 0, zIndex: 70, display: 'flex',
          alignItems: 'center', justifyContent: 'center', background: 'rgba(23,17,12,.55)',
          animation: 'fadeIn 200ms ease-out', padding: 16 }}>
        <div className="glass" onClick={(e) => e.stopPropagation()}
          style={{ padding: 30, textAlign: 'center', maxWidth: 360, width: '100%',
            animation: 'popIn 320ms cubic-bezier(.22,1,.36,1)' }}>
          <img src={logoMark} alt="Лелека принесла клієнта" width={120} height={120}
            style={{ borderRadius: '50%', objectFit: 'cover' }} />
          <h2 style={{ margin: '12px 0 4px' }}>Лелека принесла клієнта!</h2>
          <div className="num" style={{ fontSize: 34, fontWeight: 800 }}>
            +{Math.round(toast.amount).toLocaleString('uk-UA')} ₴
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
            <button onClick={() => { onCreateOrderRef.current?.(); close(); }}
              style={{ flex: 1, padding: 12, borderRadius: 10, border: 'none',
                background: 'var(--primary)', color: 'var(--primary-fg)',
                fontWeight: 700, cursor: 'pointer' }}>
              Створити замовлення
            </button>
            <button onClick={close}
              style={{ flex: 1, padding: 12, borderRadius: 10, background: 'transparent',
                color: 'var(--link)', border: '1px solid var(--border)',
                fontWeight: 600, cursor: 'pointer' }}>
              Скасувати
            </button>
          </div>
        </div>
        <style>{`@keyframes fadeIn{from{opacity:0}to{opacity:1}}
          @keyframes popIn{from{opacity:0;transform:scale(.82) translateY(16px)}to{opacity:1;transform:none}}
          @media (prefers-reduced-motion: reduce){div{animation:none!important}}`}</style>
      </div>
    ) : (
      <div role="status" aria-live="polite"
        style={{ position: 'fixed', left: '50%', bottom: 84, transform: 'translateX(-50%)',
          zIndex: 70, background: 'var(--bg-elevated)', border: '1px solid var(--border)',
          borderRadius: 12, padding: '10px 18px', boxShadow: 'var(--shadow)' }}>
        🎉 Угоду виграно · <button onClick={close}>OK</button>
      </div>
    )
  ) : null;

  return { toastEl, celebrate };
}
