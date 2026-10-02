// WCAG-контраст токенів (UI 3.5): падає, якщо звичайний текст < 4.5:1, крупний < 3:1.
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

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

const css = fs.readFileSync(path.join(__dirname, '../src/styles/tokens.css'), 'utf8');
function themeVars(theme) {
  const out = {};
  const re = theme === 'evening'
    ? /:root,\s*:root\[data-theme="evening"\]\s*{([^}]*)}/s
    : /:root\[data-theme="morning"\]\s*{([^}]*)}/s;
  const m = css.match(re);
  if (!m) return out;
  for (const mm of m[1].matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})/g)) out[mm[1]] = mm[2];
  return out;
}

const PAIRS = [
  ['text', 'bg', 4.5], ['text', 'bg-elevated', 4.5], ['text-muted', 'bg-elevated', 4.5],
  ['primary-fg', 'primary', 4.5], ['success', 'bg-elevated', 3], ['warning', 'bg-elevated', 3],
  ['danger', 'bg-elevated', 3], ['info', 'bg-elevated', 3],
];
let fail = 0;
for (const theme of ['evening', 'morning']) {
  const v = themeVars(theme);
  for (const [fg, bg, min] of PAIRS) {
    if (!v[fg] || !v[bg]) { console.log(`SKIP ${theme} ${fg}/${bg} (не hex)`); continue; }
    const r = ratio(v[fg], v[bg]);
    const ok = r >= min;
    if (!ok) fail++;
    console.log(`${ok ? 'OK  ' : 'FAIL'} ${theme} ${fg}/${bg} = ${r.toFixed(2)} (мін ${min})`);
  }
}
process.exit(fail ? 1 : 0);
