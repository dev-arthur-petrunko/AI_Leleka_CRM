const BASE = import.meta.env.VITE_API_BASE || '';

export function token(): string | null {
  return localStorage.getItem('leleka-token');
}
function refreshToken(): string | null {
  return localStorage.getItem('leleka-refresh');
}

function logout() {
  localStorage.removeItem('leleka-token');
  localStorage.removeItem('leleka-refresh');
  if (!location.pathname.endsWith('/login')) location.replace('/login');
}

/** HTTP-помилка API: статус доступний через `err.status` (402 — тариф, 403 — немає доступу). */
export class HttpError extends Error {
  status: number;
  constructor(status: number, message?: string) {
    super(message || `HTTP ${status}`);
    this.status = status;
  }
}

async function tryRefresh(): Promise<boolean> {
  const rt = refreshToken();
  if (!rt) return false;
  try {
    const r = await fetch(BASE + '/auth/refresh', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: rt }),
    });
    if (!r.ok) return false;
    const j = await r.json();
    localStorage.setItem('leleka-token', j.access_token);
    if (j.refresh_token) localStorage.setItem('leleka-refresh', j.refresh_token);
    return true;
  } catch {
    return false;
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T | null> {
  const t = token();
  if (!t) return null;
  const doFetch = async (tok: string): Promise<Response> => {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), 8000);
    try {
      return await fetch(BASE + path, {
        ...init,
        signal: ctl.signal,
        headers: { Authorization: `Bearer ${tok}`, ...(init?.headers || {}) },
      });
    } finally {
      clearTimeout(timer);
    }
  };
  let r: Response;
  try {
    const cur = token();
    if (!cur) return null;
    r = await doFetch(cur);
  } catch {
    throw new HttpError(0, 'Немає звʼязку з сервером');
  }
  if (r.status === 401) {
    // access протух — пробуємо refresh один раз, потім logout
    if (await tryRefresh()) {
      const cur = token();
      if (!cur) return null;
      try {
        r = await doFetch(cur);
      } catch {
        throw new HttpError(0, 'Немає звʼязку з сервером');
      }
      if (r.status === 401) { logout(); return null; }
    } else {
      logout();
      return null;
    }
  }
  if (!r.ok) throw new HttpError(r.status);
  if (r.status === 204) return null;
  return (await r.json()) as T;
}

export async function login(email: string, password: string, company?: string, totp?: string): Promise<void> {
  const body = new URLSearchParams({ username: email, password });
  if (company?.trim()) body.append('client_id', company.trim());
  if (totp?.trim()) body.append('scope', totp.trim());
  const r = await fetch(BASE + '/auth/login', { method: 'POST', body });
  if (r.status === 400) throw new Error('Email є у кількох компаніях — вкажіть компанію');
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const j = await r.json();
  localStorage.setItem('leleka-token', j.access_token);
  if (j.refresh_token) localStorage.setItem('leleka-refresh', j.refresh_token);
}

export async function register(email: string, password: string, ownerName: string, slug: string): Promise<void> {
  const tenant_name = slug;
  const r = await fetch(BASE + '/auth/register', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, owner_name: ownerName, tenant_name, slug }),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const j = await r.json();
  localStorage.setItem('leleka-token', j.access_token);
  if (j.refresh_token) localStorage.setItem('leleka-refresh', j.refresh_token);
}
