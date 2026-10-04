// WCAG-контраст токенів: рахуємо по РОЗВʼЯЗАНИХ кольорах.
// Кольори живуть у brand-tokens.css (hex), tokens.css може посилатись var() —
// резолвимо ланцюжки для кожної теми. Падає, якщо звичайний текст < 4.5:1.
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const dir = path.join(__dirname, '../src/styles');

function lum(hex) {
  const c = hex.replace('#', '');
  const f = (i) => {
    const v = parseInt(c.slice(i, i + 2), 16) / 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * f(0) + 0.7152 * f(2) + 0.0722 * f(4);
}
function ratio(a, b) {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
}
function blockVars(css, theme) {
  const out = {};
  // :root / :root[data-theme="X"] { ... } — збираємо всі, темний перезаписує базу
  const base = css.match(/:root\s*{([^}]*)}/s);
  const sel = `:root[data-theme="${theme}"]`;
  const idx = css.indexOf(sel);
  const chunks = [];
  if (base) chunks.push(base[1]);
  if (idx >= 0) {
    const open = css.indexOf('{', idx);
    const close = css.indexOf('}', open);
    chunks.push(css.slice(open + 1, close));
  }
  for (const ch of chunks) {
    for (const m of ch.matchAll(/--([\w-]+)\s*:\s*([^;]+);/g)) out[m[1]] = m[2].trim();
  }
  return out;
}
function resolve(vars, name, depth = 0) {
  if (depth > 6 || !vars[name]) return null;
  const v = vars[name];
  const m = v.match(/^var\(--([\w-]+)\)$/);
  if (m) return resolve(vars, m[1], depth + 1);
  return /^#[0-9a-fA-F]{6}$/.test(v) ? v : null;
}

let files = [];
for (const f of ['brand-tokens.css', 'tokens.css']) {
  const p = path.join(dir, f);
  if (fs.existsSync(p)) files.push(fs.readFileSync(p, 'utf8'));
}
const PAIRS = [
  ['text', 'bg', 4.5], ['text', 'bg-elevated', 4.5], ['text-muted', 'bg-elevated', 4.5],
  ['primary-fg', 'primary', 4.5], ['success', 'bg-elevated', 3], ['warning', 'bg-elevated', 3],
  ['danger', 'bg-elevated', 3], ['info', 'bg-elevated', 3],
];
let fail = 0, checked = 0;
for (const theme of ['evening', 'morning']) {
  const vars = {};
  for (const css of files) Object.assign(vars, blockVars(css, theme));
  for (const [fg, bg, min] of PAIRS) {
    const a = resolve(vars, fg), b = resolve(vars, bg);
    if (!a || !b) { console.log(`SKIP ${theme} ${fg}/${bg} (нема кольору)`); continue; }
    checked++;
    const r = ratio(a, b);
    const ok = r >= min;
    if (!ok) fail++;
    console.log(`${ok ? 'OK  ' : 'FAIL'} ${theme} ${fg}/${bg} = ${r.toFixed(2)} (мін ${min}) [${a}/${b}]`);
  }
}
console.log(`checked=${checked} fail=${fail}`);
process.exit(fail ? 1 : 0);
