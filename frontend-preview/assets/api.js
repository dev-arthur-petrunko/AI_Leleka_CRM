/* Спільний API-шар превʼю: реальний бекенд — першим, мок — фолбеком.
   Токен: localStorage leleka-token (ставить login.html).
   База: localStorage leleka-api або http://localhost:8000.
   Прод: той самий файл працює проти прод-домену без змін коду. */
const API_BASE = localStorage.getItem('leleka-api') || 'http://localhost:8000';
const apiToken = () => localStorage.getItem('leleka-token');

async function api(path, opts) {
  opts = opts || {};
  const t = apiToken();
  if (!t) return null;
  try {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), 4000);
    const r = await fetch(API_BASE + path, Object.assign({}, opts, {
      signal: ctl.signal,
      headers: Object.assign({ 'Authorization': 'Bearer ' + t }, opts.headers || {}),
    }));
    clearTimeout(timer);
    if (!r.ok) return null; // 401/402/404 → мовчазний фолбек на мок
    return await r.json();
  } catch (e) { return null; } // офлайн / CORS / таймаут → мок
}

async function apiLogin(email, password) {
  const r = await fetch(API_BASE + '/auth/login', {
    method: 'POST',
    body: new URLSearchParams({ username: email, password }),
  });
  if (!r.ok) throw new Error('HTTP ' + r.status);
  const j = await r.json();
  localStorage.setItem('leleka-token', j.access_token);
  return j;
}

function apiLogout() { localStorage.removeItem('leleka-token'); }
