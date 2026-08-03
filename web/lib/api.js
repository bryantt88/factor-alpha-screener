// Thin client for the FastAPI backend.
// - Production (deployed / single service): NEXT_PUBLIC_API_BASE is unset -> BASE='' -> calls hit the
//   SAME origin that served the page (FastAPI serves both the static app and /api). No CORS, no proxy.
// - Local dev (two servers): web/.env.development sets NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000 so
//   the :3000 dev server calls the :8000 backend directly (CORS allows :3000).
const BASE = process.env.NEXT_PUBLIC_API_BASE || '';

async function jf(url, opts) {
  const r = await fetch(BASE + url, opts);
  if (!r.ok) {
    let detail = `${r.status} ${r.statusText}`;
    try { detail = (await r.json()).detail || detail; } catch {}
    throw new Error(detail);
  }
  return r.json();
}

export function runScreen(body) {
  return jf('/api/screen', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}
export const listHistory = () => jf('/api/history');
export const openRun = (runId) => jf(`/api/history/${runId}`);
export const health = () => jf('/api/health');

const post = (url, body) =>
  jf(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

export const runExposure = (ticker, deep = false) => post('/api/exposure', { ticker, deep });
export const getVerdict = (b) => post('/api/exposure/verdict', b);
export const getRelStrength = (b) => post('/api/relative-strength', b);
export const explainStock = (b) => post('/api/explain', b);
