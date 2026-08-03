// Formatting + verdict-colour helpers shared across components.
export const pct = (x, d = 0) => (x == null ? 'n/a' : `${x >= 0 ? '+' : ''}${(x * 100).toFixed(d)}%`);
export const pctPts = (x, d = 1) => (x == null ? 'n/a' : `${x >= 0 ? '+' : ''}${x.toFixed(d)}%`);
export const num = (x, d = 2) => (x == null ? 'n/a' : x.toFixed(d));
// Unsigned percent (for volatility etc. where a leading '+' reads oddly).
export const pctPlain = (x, d = 0) => (x == null ? 'n/a' : `${(x * 100).toFixed(d)}%`);
// Compact money from a raw USD figure (market cap): $1.2T / $61.8B / $940M.
export const money = (x) => {
  if (x == null) return 'n/a';
  const b = x / 1e9;
  if (b >= 1000) return `$${(b / 1000).toFixed(2)}T`;
  if (b >= 1) return `$${b.toFixed(1)}B`;
  return `$${(x / 1e6).toFixed(0)}M`;
};

// Map a scorecard cell's leading glyph / track word to a verdict colour bucket (mirrors the backend).
export function verdictOf(v) {
  const s = String(v ?? '').trim();
  if (s.startsWith('✓') || s.startsWith('Rising on its own')) return 'pass';
  if (s.startsWith('✗') || s.startsWith('Just riding the wave')) return 'fail';
  if (s.startsWith('⚠') || s.includes('⚠') || s.startsWith('Turning up underneath')) return 'flag';
  if (['?', '…', '—', 'n/a', 'No clear', 'no-reg', 'equipment'].some((p) => s.startsWith(p)))
    return 'neutral';
  return '';
}

// Simple confidence tag for the own-merit return: prefer the backend's plain alphaTier when present.
export const alphaClass = (m) =>
  m.alphaSignificant ? 'pass' : (m.alphaAnnualized > 0 ? 'flag' : 'fail');
export const alphaLabel = (m) =>
  m.alphaTier || (m.alphaSignificant ? 'Real' : (m.alphaAnnualized > 0 ? 'Not proven' : 'Likely luck'));
