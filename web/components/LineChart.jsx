'use client';
// Lightweight dependency-free SVG multi-line chart (PoC). Series = [{name,color,values,dash}].
// dates = array of ISO strings (x). Draws a zero baseline + endpoint labels.
export default function LineChart({ dates, series, height = 320, yLabel = 'cumulative return (%)',
  unit = '%' }) {
  const W = 900, H = height, padL = 52, padR = 90, padT = 16, padB = 42;
  const all = series.flatMap((s) => s.values).filter((v) => v != null);
  if (!all.length) return <div className="caption">No data.</div>;
  let lo = Math.min(0, ...all), hi = Math.max(0, ...all);
  const rawSpan = (hi - lo) || 1;
  const dec = rawSpan < 3 ? 2 : (rawSpan < 30 ? 1 : 0);
  const fmt = (v) => `${v.toFixed(dec)}${unit}`;
  const fmtSigned = (v) => `${v >= 0 ? '+' : ''}${v.toFixed(dec)}${unit}`;
  const span = rawSpan; lo -= span * 0.06; hi += span * 0.06;
  const n = dates.length;
  const x = (i) => padL + (i / Math.max(n - 1, 1)) * (W - padL - padR);
  const y = (v) => padT + (1 - (v - lo) / (hi - lo)) * (H - padT - padB);
  const path = (vals) => vals.map((v, i) => (v == null ? null : `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(v).toFixed(1)}`))
    .filter(Boolean).join(' ');
  const yticks = 4;
  const ticks = Array.from({ length: yticks + 1 }, (_, k) => lo + ((hi - lo) * k) / yticks);
  const xticks = [0, Math.floor(n / 3), Math.floor((2 * n) / 3), n - 1].filter((v, i, a) => a.indexOf(v) === i);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" style={{ maxWidth: '100%' }}>
      {ticks.map((t, i) => (
        <g key={i}>
          <line x1={padL} x2={W - padR} y1={y(t)} y2={y(t)} stroke="#EEF1F5" />
          <text x={padL - 8} y={y(t) + 4} textAnchor="end" fontSize="11" fill="#94A3B8" fontFamily="monospace">
            {fmt(t)}
          </text>
        </g>
      ))}
      <line x1={padL} x2={W - padR} y1={y(0)} y2={y(0)} stroke="#94A3B8" strokeDasharray="3 3" />
      {xticks.map((i) => (
        <text key={i} x={x(i)} y={H - padB + 20} textAnchor="middle" fontSize="11" fill="#94A3B8">
          {dates[i]?.slice(0, 7)}
        </text>
      ))}
      {series.map((s, si) => {
        const last = [...s.values].reverse().find((v) => v != null);
        const lastI = s.values.length - 1 - [...s.values].reverse().findIndex((v) => v != null);
        return (
          <g key={si}>
            <path d={path(s.values)} fill="none" stroke={s.color} strokeWidth="2.2"
              strokeDasharray={s.dash || 'none'} strokeLinejoin="round" />
            {last != null && (
              <text x={x(lastI) + 6} y={y(last) + 4} fontSize="11" fill={s.color} fontFamily="monospace">
                {fmtSigned(last)}
              </text>
            )}
          </g>
        );
      })}
      <text x={14} y={H / 2} transform={`rotate(-90 14 ${H / 2})`} textAnchor="middle" fontSize="11" fill="#94A3B8">
        {yLabel}
      </text>
    </svg>
  );
}
