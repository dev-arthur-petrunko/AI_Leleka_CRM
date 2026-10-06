import { useCallback, useEffect, useRef, useState } from 'react';
import { PartyPopper } from 'lucide-react';
import logoMark from './assets/brand/logo-mark.png';
import posePack from './assets/brand/pose-laptop.webp';
import { loadAnim, loadCelebration } from './theme';

export type { AnimMode } from './theme';

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

export function celebrationMode() {
  return loadAnim();
}

/** Велика угода — завжди повний екран (крім min/off). */
export function isBigWin(amount: number): boolean {
  return amount >= 50000;
}

/** Єдиний хук свята виграшу — канбан, таблиця, drawer. Повертає JSX тосту. */
export function useDealWonCelebration() {
  const [toast, setToast] = useState<null | { dealId: string; amount: number }>(null);
  const [spectacle, setSpectacle] = useState(false);
  const [flyKey, setFlyKey] = useState(0);
  const timer = useRef<number | null>(null);
  const onCreateOrderRef = useRef<(() => void) | null>(null);
  const prevFocus = useRef<HTMLElement | null>(null);
  const dialogRef = useRef<HTMLDivElement | null>(null);

  const close = useCallback(() => {
    setToast(null);
    setSpectacle(false);
    // повертаємо фокус туди, де був користувач
    prevFocus.current?.focus?.();
    prevFocus.current = null;
  }, []);

  // Esc закриває повноекранне свято
  useEffect(() => {
    if (!spectacle) return;
    const h = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
    };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [spectacle, close]);

  // фокус у діалог при відкритті
  useEffect(() => {
    if (spectacle) dialogRef.current?.focus();
  }, [spectacle]);

  const celebrate = useCallback(async ({ dealId, amount, anchorEl, onCreateOrder }: CelebrateArgs) => {
    if (!shouldCelebrate(dealId)) return;
    const mode = celebrationMode();
    if (mode === 'off') return;
    onCreateOrderRef.current = onCreateOrder;
    prevFocus.current = document.activeElement as HTMLElement | null;
    setToast({ dealId, amount });
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => { setToast(null); setSpectacle(false); }, 8000);
    const big = isBigWin(amount);
    const full = mode === 'all' && (loadCelebration() === 'full' || big);
    setSpectacle(full);
    if (mode !== 'all') return; // «Мінімум»: тихий тост без конфетті
    if (!full) setFlyKey((k) => k + 1); // компакт: лелека пролетить з пакетом
    const rect = anchorEl?.getBoundingClientRect();
    const origin = rect
      ? { x: (rect.left + rect.width / 2) / window.innerWidth, y: Math.min(0.9, rect.top / window.innerHeight) }
      : { x: 0.5, y: 0.4 };
    const { default: confetti } = await import('canvas-confetti');
    confetti({
      particleCount: full ? (window.innerWidth < 768 ? 60 : big ? 140 : 90) : 45,
      spread: 110, origin, disableForReducedMotion: true,
      colors: ['#BD5A2A', '#2C5A5B', '#F7F2E9', '#D9A441', '#ffffff'],
    });
    if (big && full) {
      window.setTimeout(() => confetti({
        particleCount: 80, spread: 130, origin: { x: 0.5, y: 0.3 },
        colors: ['#BD5A2A', '#D9A441', '#ffffff'], disableForReducedMotion: true,
      }), 450);
    }
  }, []);

  const toastEl = (
    <>
      {flyKey > 0 && toast && !spectacle && (
        <img key={flyKey} src={posePack} alt="" aria-hidden
          className="fly-by" width={110} height={110} />
      )}
      {toast && spectacle && (
        <div role="dialog" aria-modal="true" aria-label="Угоду виграно" onClick={close}
          ref={dialogRef} tabIndex={-1}
          style={{ position: 'fixed', inset: 0, zIndex: 70, display: 'flex',
            alignItems: 'center', justifyContent: 'center', background: 'rgba(23,17,12,.55)',
            padding: 16, outline: 'none' }}>
          <div className="glass drawer-in" onClick={(e) => e.stopPropagation()}
            style={{ padding: 30, textAlign: 'center', maxWidth: 360, width: '100%' }}>
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
              <button onClick={close} aria-label="Закрити (Esc)"
                style={{ flex: 1, padding: 12, borderRadius: 10, background: 'transparent',
                  color: 'var(--link)', border: '1px solid var(--border)',
                  fontWeight: 600, cursor: 'pointer' }}>
                Закрити
              </button>
            </div>
          </div>
        </div>
      )}
      {toast && !spectacle && (
        <div role="status" aria-live="polite" className="toast-in"
          style={{ position: 'fixed', right: 16, bottom: 76, zIndex: 70, maxWidth: 340,
            background: 'var(--bg-elevated)', border: '1px solid var(--border)',
            borderRadius: 12, padding: '10px 14px', boxShadow: 'var(--shadow)',
            display: 'flex', gap: 10, alignItems: 'center', pointerEvents: 'auto' }}>
          <PartyPopper size={20} aria-hidden style={{ color: 'var(--warning)', flex: 'none' }} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <b>Угоду виграно</b>
            <div className="num" style={{ fontWeight: 800 }}>
              +{Math.round(toast.amount).toLocaleString('uk-UA')} ₴
            </div>
          </div>
          <button onClick={() => { onCreateOrderRef.current?.(); close(); }}
            style={{ padding: '8px 12px', borderRadius: 8, border: 'none',
              background: 'var(--primary)', color: 'var(--primary-fg)',
              fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap' }}>
            Замовлення
          </button>
          <button onClick={close} aria-label="Закрити"
            style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)',
              cursor: 'pointer', fontSize: 16, padding: 4 }}>×</button>
        </div>
      )}
    </>
  );

  return { toastEl, celebrate };
}
