/* API-шар превʼю v2 (фаза 1.8): чесні відповіді замість мовчазних моків.
   api() -> {ok:true,data} | {ok:false,error,status}
   - нема звʼязку: червоний банер «Немає звʼязку з сервером»
   - ?demo=1: явний демо-режим з плашкою «Демо» (єдине місце, де моки дозволені)
   - 401: редирект на login.html; 402: банер з пропозицією тарифу
   Токен: localStorage leleka-token (ставить login.html). */
const API_BASE = localStorage.getItem('leleka-api') || 'http://localhost:8000';
const apiToken = () => localStorage.getItem('leleka-token');
const DEMO_MODE = new URLSearchParams(location.search).get('demo') === '1';

function showBanner(html) {
  let el = document.getElementById('api-banner');
  if (!el) {
    el = document.createElement('div');
    el.id = 'api-banner';
    el.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:100;background:#b91c1c;color:#fff;' +
      'font-size:13.5px;text-align:center;padding:9px 12px;';
    document.body.prepend(el);
  }
  el.innerHTML = html;
  el.style.display = 'block';
}
function hideBanner() {
  const el = document.getElementById('api-banner');
  if (el) el.style.display = 'none';
}
if (DEMO_MODE) {
  document.addEventListener('DOMContentLoaded', () => showBanner('🧪 Демо-режим (?demo=1): показано НЕ ваші дані'));
}

async function api(path, opts) {
  opts = opts || {};
  const t = apiToken();
  if (!t) return { ok: false, error: 'no-token' };
  try {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), 8000);
    const r = await fetch(API_BASE + path, Object.assign({}, opts, {
      signal: ctl.signal,
      headers: Object.assign({ 'Authorization': 'Bearer ' + t }, opts.headers || {}),
    }));
    clearTimeout(timer);
    if (r.status === 401) {
      if (!location.pathname.endsWith('login.html')) location = 'login.html';
      return { ok: false, error: 'unauthorized', status: 401 };
    }
    if (r.status === 402) {
      showBanner('💳 Потрібен платний тариф. <a href="billing.html" style="color:#fff;font-weight:700">Обрати тариф →</a>');
      return { ok: false, error: 'payment-required', status: 402 };
    }
    if (!r.ok) return { ok: false, error: 'http-' + r.status, status: r.status };
    hideBanner();
    return { ok: true, data: await r.json() };
  } catch (e) {
    showBanner('🔌 Немає звʼязку з сервером. Показано не ваші дані.');
    return { ok: false, error: 'offline' };
  }
}

async function apiLogin(email, password, company) {
  const params = { username: email, password };
  if (company) params.client_id = company;
  const r = await fetch(API_BASE + '/auth/login', {
    method: 'POST',
    body: new URLSearchParams(params),
  });
  if (!r.ok) throw new Error('HTTP ' + r.status);
  const j = await r.json();
  localStorage.setItem('leleka-token', j.access_token);
  if (j.refresh_token) localStorage.setItem('leleka-refresh', j.refresh_token);
  return j;
}

function apiLogout() {
  localStorage.removeItem('leleka-token');
  localStorage.removeItem('leleka-refresh');
}
