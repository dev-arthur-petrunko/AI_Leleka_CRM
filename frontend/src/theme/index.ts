export type ThemeMode = 'auto-time' | 'morning' | 'evening' | 'system' | 'telegram';
export type Theme = 'morning' | 'evening';

declare global {
  interface Window {
    Telegram?: { WebApp?: { colorScheme?: string } };
  }
}

export function resolveTheme(mode: ThemeMode, now = new Date(), tz = 'Europe/Kyiv'): Theme {
  if (mode === 'morning' || mode === 'evening') return mode;
  if (mode === 'system')
    return matchMedia('(prefers-color-scheme: dark)').matches ? 'evening' : 'morning';
  if (mode === 'telegram')
    return window.Telegram?.WebApp?.colorScheme === 'dark' ? 'evening' : 'morning';
  const hour = Number(
    new Intl.DateTimeFormat('en-GB', { hour: '2-digit', hour12: false, timeZone: tz }).format(now),
  );
  return hour >= 7 && hour < 19 ? 'morning' : 'evening';
}

export type AnimMode = 'all' | 'min' | 'off';

export function applyTheme(t: Theme) {
  const swap = () => {
    document.documentElement.dataset.theme = t;
  };
  const w = window as unknown as { document?: Document & {
    startViewTransition?: (cb: () => void) => { finished: Promise<void> } } };
  try {
    if (w.document?.startViewTransition) w.document.startViewTransition(swap);
    else swap();
  } catch {
    swap();
  }
}

/** Режим анімацій: атрибут <html> — сервер, localStorage — швидкий кеш. */
export function applyAnim(m: AnimMode) {
  document.documentElement.dataset.anim = m;
  try {
    localStorage.setItem('leleka.animations', m);
  } catch {
    /* ignore */
  }
}

export function loadAnim(): AnimMode {
  try {
    const a = document.documentElement.dataset.anim
      || localStorage.getItem('leleka.animations');
    if (a === 'min' || a === 'off') return a;
  } catch {
    /* ignore */
  }
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return 'min';
  return 'all';
}

export function loadMode(): ThemeMode {
  try {
    return (localStorage.getItem('leleka.themeMode') as ThemeMode) || 'auto-time';
  } catch {
    return 'auto-time';
  }
}

export function saveMode(m: ThemeMode) {
  try {
    localStorage.setItem('leleka.themeMode', m);
  } catch {
    /* ignore */
  }
}
