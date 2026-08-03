'use client';
// Dependency-free SVG scatter for the regression fit: predicted vs actual daily return (%), + y=x line.
export default function ScatterChart({ x, y, height = 340, xLabel = 'model-predicted daily return (%)',
  yLabel = 'actual daily return (%)', note = '' }) {
  const W = 900, H = height, pad = 52;
  const pts = x.map((xi, i) => [xi, y[i]]).filter(([a, b]) => a != null && b != null);
  if (!pts.length) return <div className="caption">No data.</div>;
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  const lo = Math.min(...xs, ...ys), hi = Math.max(...xs, ...ys);
  const span = hi - lo || 1, LO = lo - span * 0.05, HI = hi + span * 0.05;
  const sx = (v) => pad + ((v - LO) / (HI - LO)) * (W - pad * 2);
  const sy = (v) => H - pad - ((v - LO) / (HI - LO)) * (H - pad * 2);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ maxWidth: '100%' }} role="img">
      <line x1={sx(LO)} y1={sy(LO)} x2={sx(HI)} y2={sy(HI)} stroke="#94A3B8" strokeDasharray="6 4" />
      {pts.map(([a, b], i) => (
        <circle key={i} cx={sx(a)} cy={sy(b)} r="3" fill="#16A34A" fillOpacity="0.5" />
      ))}
      <text x={W / 2} y={H - 12} textAnchor="middle" fontSize="11" fill="#94A3B8">{xLabel}</text>
      <text x={16} y={H / 2} transform={`rotate(-90 16 ${H / 2})`} textAnchor="middle" fontSize="11" fill="#94A3B8">{yLabel}</text>
      {note && <text x={pad + 6} y={pad} fontSize="12" fill="#0F172A" fontFamily="monospace">{note}</text>}
    </svg>
  );
}
