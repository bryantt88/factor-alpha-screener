'use client';
import { Fragment } from 'react';
import { num, pct, alphaClass, alphaLabel } from '@/lib/format';

// Driver-group colours (mirror viz/charts.GROUP_COLORS; idiosyncratic = the idio green).
const GROUP_COLOR = {
  Market: '#1f5c8a', Rates: '#6b5b95', Energy: '#8c564b',
  Sector: '#0e7c86', Style: '#c26a1b', Macro: '#a24d7a', Idiosyncratic: '#14663A',
};
const GREEN = '#14663A', RED = '#97231F';
const fmtCorr = (x) => (x == null ? '—' : `${x >= 0 ? '+' : ''}${x.toFixed(2)}`);

// ---- Return Bridge: raw price move vs the stock's OWN story (idiosyncratic) ----
// Both bars are the COMPOUNDED numbers already shown in the header — no second (additive) set of
// numbers to reconcile. The idiosyncratic return is literally raw minus everything the factors explain;
// the gap between the two bars IS the factor contribution (described in words, not a third number).
function DivBar({ label, value, maxAbs, strong }) {
  const frac = Math.min(Math.abs(value) / (maxAbs || 1), 1) * 50;
  const pos = value >= 0;
  const color = pos ? GREEN : RED;
  return (
    <div className="bridge-row">
      <div className="blabel" style={{ fontWeight: strong ? 800 : 600 }}>{label}</div>
      <div className="btrack">
        <div className="bcenter" />
        <div className="bbar" style={{ left: pos ? '50%' : `${50 - frac}%`, width: `${frac}%`,
          background: color, opacity: strong ? 1 : 0.82 }} />
      </div>
      <div className="bval" style={{ color }}>{pct(value)}</div>
    </div>
  );
}

function ReturnBridge({ raw, own }) {
  if (raw == null || own == null) return null;
  const maxAbs = Math.max(Math.abs(raw), Math.abs(own), 0.01);
  const R = pct(raw), O = pct(own);
  let read;
  if (raw > 0.005) {
    if (own <= -0.005) read = <>It rose {R}, but strip out the market, sector and style and its <b>own</b> return was {O} — a drag. The gain is a <b>factor / market ride</b>, not an own-story.</>;
    else if (own >= raw * 0.5) read = <>A large part of the {R} move is the stock's <b>own story</b> ({O}) — not just the factor tide.</>;
    else read = <>Of the {R} move, {O} was the stock's <b>own story</b>; the rest came from the market / sector / factor tide.</>;
  } else if (raw < -0.005) {
    read = own >= 0.005
      ? <>Price fell {R}, but its <b>own story is positive</b> ({O}) — turning up underneath the factor tide.</>
      : <>Price fell {R}, and its own story ({O}) offers no offset.</>;
  } else {
    read = <>Roughly flat overall; the stock's own story is {O}.</>;
  }
  return (
    <div>
      <div className="bridge">
        <DivBar label="Raw return (price)" value={raw} maxAbs={maxAbs} />
        <DivBar label="Own-story return (idiosyncratic)" value={own} maxAbs={maxAbs} strong />
      </div>
      <div className="caption" style={{ marginTop: 10 }}>
        The <b>idiosyncratic (own-story) return is the leftover</b> — the raw price move minus everything the
        market, sector, style and macro factors explain. The gap between the two bars is what those factors
        contributed. {read}
        <br /><span style={{ fontSize: '.92em' }}>Both are compounded — the same two numbers shown up top, nothing else to reconcile.</span>
      </div>
    </div>
  );
}

// ---- Variance bars: what DRIVES the stock day-to-day (Shapley/LMG, proportional 0-100% track) ----
function DriverBars({ groups }) {
  return (
    <>
      <div className="drivers">
        {groups.map((g) => (
          <div className="drow" key={g.name}>
            <div className="dlabel">{g.name}{g.unstable ? ' ⚠' : ''}</div>
            <div className="dbar-wrap">
              <div className="dbar" style={{ width: `${Math.max(g.share, 0)}%`,
                background: GROUP_COLOR[g.name] || '#888' }} />
            </div>
            <div className="dval">{g.share.toFixed(0)}%</div>
          </div>
        ))}
      </div>
      <div className="drivers-axis">
        <div className="ticks"><span>0%</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span></div>
      </div>
    </>
  );
}

// JPM factor table: per-factor 6M / 1Y univariate correlation, grouped by driver group.
function FactorTable({ rows }) {
  if (!rows || !rows.length) return null;
  const order = [];
  const byGroup = {};
  rows.forEach((r) => { if (!byGroup[r.group]) { byGroup[r.group] = []; order.push(r.group); } byGroup[r.group].push(r); });
  return (
    <div className="tablewrap" style={{ marginTop: 12 }}>
      <table className="sc factab">
        <thead><tr><th>Factor</th><th>6M corr</th><th>1Y corr</th></tr></thead>
        <tbody>
          {order.map((gr) => (
            <Fragment key={gr}>
              <tr className="grp"><td colSpan={3}>{gr}</td></tr>
              {byGroup[gr].map((r) => (
                <tr key={r.factor}>
                  <td style={{ paddingLeft: 24 }}>{r.label}</td>
                  <td className="mono">{fmtCorr(r.corr6m)}</td>
                  <td className="mono">{fmtCorr(r.corr1y)}</td>
                </tr>
              ))}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function DriversPanel({ s, driversCaveat }) {
  const drivers = s.drivers, factorTable = s.factorTable, m = s.metrics;
  const hasVar = drivers && drivers.groups;
  const idio = hasVar ? (drivers.groups.find((g) => g.name === drivers.idioKey) || { share: 0 }) : null;
  const explained = hasVar && drivers.r2Adjusted != null ? drivers.r2Adjusted * 100 : null;
  const stab = hasVar ? drivers.stability : null;
  const unstable = stab && stab.unstableGroups.length;

  return (
    <div>
      <div className="metrics" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginTop: 4 }}>
        <div className="metric" title="1 − adjusted R². Share of this stock's day-to-day VARIANCE (risk / wiggle) the factors can't explain. A RISK measure — NOT a slice of the return, so it won't equal the own-story return below.">
          <div className="lbl">Own share of risk</div><div className="v num">{idio ? `${idio.share.toFixed(0)}%` : '—'}</div>
        </div>
        <div className="metric" title="Adjusted R² — share of day-to-day variance (risk) explained by all driver groups together.">
          <div className="lbl">Risk from factors</div><div className="v num">{explained == null ? '—' : `${explained.toFixed(0)}%`}</div>
        </div>
        <div className="metric" title="Annualized idiosyncratic alpha ÷ idiosyncratic risk. The quality of the own-story return — the ranking metric.">
          <div className="lbl">Information ratio</div><div className="v num">{num(m.informationRatio)}</div>
        </div>
        <div className="metric" title="Is the own-story drift statistically real? Real (t≥2) · Not proven (1–2) · Likely luck (<1).">
          <div className="lbl">Confidence</div>
          <div className="v"><span className={`pill ${alphaClass(m)}`}>{alphaLabel(m)}</span></div>
        </div>
      </div>

      <div className="eyebrow" style={{ margin: '20px 0 8px' }}>Where the return came from</div>
      <ReturnBridge raw={m.raw12m} own={m.idioEndpoint} />

      {hasVar && (
        <>
          <div className="eyebrow" style={{ margin: '22px 0 8px' }}>What drives it day-to-day · share of variance</div>
          <DriverBars groups={drivers.groups} />
          <div className="caption" style={{ marginTop: 12 }}>Each bar = the share of this stock's day-to-day variance driven by that group
            (Shapley/LMG split, sums to 100%). This is a <b>risk</b> measure — <b>not</b> a slice of the return: a 48%
            idiosyncratic risk share does <b>not</b> mean 48% of the return, so don't multiply it by the raw return. Risk
            (this panel) and return (the bridge above) are separate.
            {unstable ? <> ⚠ <b>{stab.unstableGroups.join(', ')}</b> swing between the 6M and 1Y windows, read with caution.</> : ''}
          </div>
        </>
      )}

      {hasVar && (
        <details className="diag" style={{ marginTop: 18 }}>
          <summary>Factor correlations (6M vs 1Y)</summary>
          <div className="diagbody">
            <FactorTable rows={factorTable} />
            <div className="caption">Univariate correlation of the stock with each factor — distinct from the
              model's partial betas. A big 6M-vs-1Y gap = a changing relationship.</div>
            {driversCaveat && <div className="caption">ℹ️ {driversCaveat}</div>}
          </div>
        </details>
      )}
      {!hasVar && <div className="caption" style={{ marginTop: 14 }}>The full variance driver split (Market / Sector / Style / Macro …)
        only renders in the <b>drivers</b> factor mode. This run uses <b>{s.betas ? Object.keys(s.betas).length : 0}</b> factors.</div>}
    </div>
  );
}
