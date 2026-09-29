const BASE = import.meta.env.VITE_API_BASE || '';

export function token(): string | null {
  return localStorage.getItem('leleka-token');
}

export async function api<T>(path: string, init?: RequestInit): Promise<T | null> {
  const t = token();
  if (!t) return null;
  try {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), 8000);
    const r = await fetch(BASE + path, {
      ...init,
      signal: ctl.signal,
      headers: { Authorization: `Bearer ${t}`, 'Content-Type': 'application/json', ...(init?.headers || {}) },
    });
    clearTimeout(timer);
    if (!r.ok) return null;
    return (await r.json()) as T;
  } catch {
    return null;
  }
}

export async function login(email: string, password: string): Promise<void> {
  const r = await fetch(BASE + '/auth/login', {
    method: 'POST',
    body: new URLSearchParams({ username: email, password }),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const j = await r.json();
  localStorage.setItem('leleka-token', j.access_token);
}
