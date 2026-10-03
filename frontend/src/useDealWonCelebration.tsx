import { useCallback, useRef, useState } from 'react';

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
  const timer = useRef<number | null>(null);

  const celebrate = useCallback(async ({ dealId, amount, anchorEl, onCreateOrder }: CelebrateArgs) => {
    if (!shouldCelebrate(dealId)) return;
    const mode = celebrationMode();
    if (mode === 'off') return;
    setToast({ dealId, amount });
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setToast(null), 8000);
    if (mode === 'min' || reducedMotion()) return; // тільки підсвітка + тост
    const rect = anchorEl?.getBoundingClientRect();
    const origin = rect
      ? { x: (rect.left + rect.width / 2) / window.innerWidth, y: rect.top / window.innerHeight }
      : { y: 0.6 };
    const big = amount >= 50000;
    const { default: confetti } = await import('canvas-confetti');
    confetti({
      particleCount: big ? 120 : window.innerWidth < 768 ? 25 : 50,
      spread: 70, origin,
      colors: ['#BD5A2A', '#2C5A5B', '#F7F2E9', '#D9A441'],
      disableForReducedMotion: true,
    });
  }, []);

  const onCreateOrderRef = useRef<(() => void) | null>(null);

  const toastEl = toast ? (
    <div role="status" aria-live="polite"
      style={{ position: 'fixed', right: 16, bottom: 16, zIndex: 60, maxWidth: 340,
        background: 'var(--bg-elevated)', border: '1px solid var(--border)',
        borderRadius: 12, padding: 14, boxShadow: 'var(--shadow)' }}>
      <b>🎉 Лелека принесла клієнта! +{Math.round(toast.amount).toLocaleString('uk-UA')} ₴</b>
      <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
        <button onClick={() => { onCreateOrderRef.current?.(); setToast(null); }}>
          Створити замовлення
        </button>
        <button onClick={() => setToast(null)}>Скасувати</button>
      </div>
    </div>
  ) : null;

  return {
    toastEl,
    celebrate: (a: CelebrateArgs) => {
      onCreateOrderRef.current = a.onCreateOrder;
      return celebrate(a);
    },
  };
}
