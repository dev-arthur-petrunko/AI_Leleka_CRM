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

export function applyTheme(t: Theme) {
  document.documentElement.dataset.theme = t;
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
