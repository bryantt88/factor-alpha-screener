'use client';
import { useState } from 'react';
import LineChart from './LineChart';
import ScatterChart from './ScatterChart';
import DriversPanel from './Drivers';
import { runExposure, getVerdict, getRelStrength, explainStock } from '@/lib/api';
import { pct, pctPts, pctPlain, num, money, verdictOf, alphaClass, alphaLabel } from '@/lib/format';

const C_IDIO = '#14663A', C_RAW = '#8B98A8';
const FCOLOR = { oil: '#8c564b', brent: '#a0522d', gas: '#c26a1b', market: '#1f5c8a', rates: '#6b5b95' };
const OIL_CAVEAT = 'Oil/gas factors use front-month futures (CL=F / NG=F): monthly rolls + a non-synchronous close attenuate the commodity betas, which can push genuine commodity moves into the idiosyncratic (α+ε). Read α+ε alongside R².';
const STATUS_PILL = { pass: 'pass', fail: 'fail', flag: 'flag', unverified: 'neutral', pending: 'neutral' };
const FUND_LABEL = {
  ebitda_margin: 'EBITDA margin (+ YoY)', net_debt_to_ebitda: 'Net debt / EBITDA',
  earnings_surprise: 'EPS surprise', valuation: 'EV / EBITDA',
};

function Legend({ items }) {
  return (
    <div className="legend">
      {items.map((it, i) => (
        <span className="k" key={i}>
          <span className="swatch" style={{ background: it.dash ? 'transparent' : it.color,
            borderTop: it.dash ? `2px dashed ${it.color}` : 'none', height: it.dash ? 0 : 3 }} />
          {it.label}
        </span>
      ))}
    </div>
  );
}

function Section({ n, title, tag, sub, children }) {
  return (
    <section className="section">
      <div className="sechead">
        <span className="secnum">{n}</span><h3>{title}</h3>
        {tag && <span className="tag">{tag}</span>}
      </div>
      {sub && <div className="secsub">{sub}</div>}
      {children}
    </section>
  );
}

// ---------- ranked summary (click a row to open its report) ----------
function Summary({ stocks, gates, sel, onSelect }) {
  return (
    <div className="summary">
      <div className="srow head">
        <div className="s-rank">#</div><div>Ticker</div><div>Verdict</div>
        <div style={{ textAlign: 'right' }}>Confidence</div>
        <div style={{ textAlign: 'right' }}>Info ratio</div>
        <div style={{ textAlign: 'right' }}>Idiosyncr.</div>
        <div style={{ textAlign: 'right' }}>Mkt cap</div>
      </div>
      {stocks.map((s, i) => {
        const v = verdictOf(s.trackShort) || 'neutral';
        const mc = gates[s.ticker]?.size?.marketCap;
        return (
          <div key={s.ticker} className={`srow ${sel === s.ticker ? 'sel' : ''}`} onClick={() => onSelect(s.ticker)}>
            <div className="s-rank">{i + 1}</div>
            <div className="s-tk">{s.ticker}</div>
            <div className="s-verdict"><span className={`s-dot ${v}`} />{s.trackShort}</div>
            <div style={{ textAlign: 'right' }}><span className={`pill ${alphaClass(s.metrics)}`}>{alphaLabel(s.metrics)}</span></div>
            <div className="s-num">{num(s.metrics.informationRatio)}</div>
            <div className="s-num">{pct(s.metrics.idioEndpoint)}</div>
            <div className="s-num">{money(mc)}</div>
          </div>
        );
      })}
    </div>
  );
}

// ---------- Gate-3 AI-exposure: AI grades strong/moderate/low/none, you approve or override --------
const GRADE_PILL = { strong: 'pass', moderate: 'pass', low: 'flag', none: 'fail' };
const GRADE_LABEL = { strong: 'Strong', moderate: 'Moderate', low: 'Low', none: 'None' };

function ExposureFlow({ ticker, config, geminiAvailable }) {
  const [prop, setProp] = useState(null);
  const [loading, setLoading] = useState('');       // '' | 'news' | 'web'
  const [type, setType] = useState('');
  const [grade, setGrade] = useState('');           // final grade (AI's, or overridden)
  const [verdict, setVerdict] = useState(null);
  const [rel, setRel] = useState(null);
  const [err, setErr] = useState('');

  async function run(deep) {
    setLoading(deep ? 'web' : 'news'); setErr(''); setVerdict(null); setRel(null);
    try {
      const p = await runExposure(ticker, deep);
      setProp(p); setType(p.type); setGrade(p.grade);
    } catch (e) { setErr(String(e.message || e)); }
    finally { setLoading(''); }
  }
  async function decide(d) {
    try {
      const v = await getVerdict({ grade, type, error: prop.error, decision: d });
      setVerdict(v);
      if (d === 'approved') {
        const r = await getRelStrength({ ticker, type, factorSet: config.factorSet, horizon: config.horizon });
        setRel(r);
      }
    } catch (e) { setErr(String(e.message || e)); }
  }

  if (!geminiAvailable) return <div className="caption">Gemini CLI not available — AI-exposure agent disabled.</div>;
  const grades = (prop && prop.grades) || ['strong', 'moderate', 'low', 'none'];
  return (
    <div>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <button className="btn ghost" onClick={() => run(false)} disabled={!!loading}>
          {loading === 'news' ? 'Reading recent news…' : `🔎 Grade ${ticker} (recent news, ~25s)`}
        </button>
        {prop && (
          <button className="btn ghost" onClick={() => run(true)} disabled={!!loading}
            title="Live web search — catches older/structural deals recent headlines miss">
            {loading === 'web' ? 'Searching the web (~2 min)…' : '🌐 Deep web search (~2 min)'}
          </button>
        )}
      </div>
      {err && <div className="err" style={{ marginTop: 10 }}>{err}</div>}
      {prop && !prop.error && (
        <div style={{ marginTop: 12 }}>
          <div className="verdict" style={{ marginBottom: 6 }}>
            <b>AI read:</b>{' '}
            <span className={`pill ${GRADE_PILL[prop.grade] || 'neutral'}`}>{GRADE_LABEL[prop.grade] || prop.grade} AI exposure</span>{' '}
            <span className="caption" style={{ margin: 0 }}>· via {prop.mode === 'web' ? 'live web search' : `${prop.nSources} recent news items`} · type: {prop.type}</span>
          </div>
          {prop.comment && <div className="verdict" style={{ marginTop: 4 }}><b>🧠 Agent's view:</b> {prop.comment}</div>}
          {prop.bullets.length > 0 ? (
            <>
              <div className="callout" style={{ marginTop: 8 }}>⚠ {prop.mode === 'web' ? 'Web-sourced' : 'Proposed'} — verify each source link before approving.</div>
              <ul>
                {prop.bullets.map((b, i) => (
                  <li key={i}><b>[{b.status}]</b> {b.claim} — <a href={b.source} target="_blank" rel="noreferrer">🔗 source</a></li>
                ))}
              </ul>
            </>
          ) : <div className="caption">No sourced evidence bullets — the grade reflects the agent's read of the business{prop.mode === 'news' ? ' (try Deep web search for fresh sources)' : ''}.</div>}

          <div className="row2" style={{ maxWidth: 520, marginTop: 8 }}>
            <div className="field">
              <label>Final grade (you decide — overrides the AI)</label>
              <select className="select" value={grade} onChange={(e) => setGrade(e.target.value)}>
                {grades.map((g) => <option key={g} value={g}>{GRADE_LABEL[g] || g}</option>)}
              </select>
            </div>
            <div className="field">
              <label>Type (benchmark for relative strength)</label>
              <select className="select" value={type} onChange={(e) => setType(e.target.value)}>
                {(prop.types || []).concat(prop.types.includes(type) ? [] : [type]).map((t) => <option key={t}>{t}</option>)}
              </select>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button className="btn" onClick={() => decide('approved')}>✅ Approve ({GRADE_LABEL[grade] || grade})</button>
            <button className="btn ghost" onClick={() => decide('rejected')}>❌ Reject</button>
          </div>
          {verdict && (
            <div className="verdict" style={{ marginTop: 10 }}>
              <b>Gate verdict:</b>{' '}
              <span className={`pill ${STATUS_PILL[verdict.status] || 'neutral'}`}>{verdict.status}</span> — {verdict.note}
            </div>
          )}
          {rel && rel.series && (
            <div style={{ marginTop: 12 }}>
              <LineChart dates={rel.series.dates} series={[{ name: `${ticker} − ${rel.benchmark}`, color: C_IDIO, values: rel.series.values }]}
                yLabel={`excess vs ${rel.benchmark} (pts)`} unit="" height={260} />
              <div className="caption">Rising = beating its sector benchmark ({rel.benchmark}); above 0 = an AI premium over the sector tide.</div>
            </div>
          )}
          {rel && !rel.series && <div className="caption">{rel.note}</div>}
        </div>
      )}
      {prop && prop.error && <div className="err" style={{ marginTop: 10 }}>Agent error: {prop.error}</div>}
    </div>
  );
}

// ---------- diagnostics (collapsed by default) ----------
function AttributionTable({ attr, rawCompounded }) {
  const total = attr.total;
  const share = (v) => (total !== 0 ? `${((v / total) * 100).toFixed(0)}%` : '—');
  return (
    <div>
      <table className="sc">
        <thead><tr><th>slice</th><th>contribution (pts, additive)</th><th>share of move</th></tr></thead>
        <tbody>
          {attr.slices.map((sl) => (
            <tr key={sl.name}>
              <td>{sl.name === attr.idioKey ? 'Own (α+ε)' : sl.name}</td>
              <td className="mono">{pctPts(sl.pct)}</td>
              <td className="mono">{share(sl.pct)}</td>
            </tr>
          ))}
          <tr><td><b>Total (additive)</b></td><td className="mono"><b>{pctPts(total)}</b></td><td className="mono">100%</td></tr>
        </tbody>
      </table>
      <div className="caption" style={{ marginTop: 8 }}>Additive breakdown (Σ of daily returns), so slices sum linearly to the
        additive total (compounded raw = <b>{pct(rawCompounded)}</b>). In multi-factor mode the collinear factors can produce
        large <b>offsetting</b> slices (e.g. market +90, style −90) that net out — which is exactly why the headline read
        above uses the clean <b>factors-vs-own-story</b> split, not these raw per-factor slices.</div>
    </div>
  );
}

function Diagnostics({ s, config }) {
  const [tab, setTab] = useState('trend');
  const m = s.metrics;
  const oil = config.factorLogical?.some((f) => f === 'oil' || f === 'gas');
  const tabs = [['trend', 'Raw vs idiosyncratic'], ['fit', 'Regression fit'],
    ['attr', 'Attribution (detailed)']];
  return (
    <details className="diag">
      <summary>Diagnostics — regression fit & detailed attribution (for the analyst)</summary>
      <div className="diagbody">
        <div className="seg" style={{ marginTop: 12, flexWrap: 'wrap' }}>
          {tabs.map(([k, l]) => <button key={k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{l}</button>)}
        </div>
        {tab === 'trend' && (
          <div style={{ marginTop: 14 }}>
            <LineChart dates={s.series.raw.dates} series={[
              { name: 'raw', color: C_RAW, values: s.series.raw.values },
              { name: 'idiosyncratic (α+ε)', color: C_IDIO, values: s.series.idio.values },
            ]} />
            <Legend items={[
              { color: C_RAW, label: 'raw return — the actual price move (compounded)' },
              { color: C_IDIO, label: 'idiosyncratic (α+ε) — after stripping the factors' },
            ]} />
            <div className="caption">The gap between the lines = the part explained by the factors. Both compounded.
              {oil && <> ℹ️ {OIL_CAVEAT}</>}</div>
          </div>
        )}
        {tab === 'fit' && (
          <div style={{ marginTop: 14 }}>
            <ScatterChart x={s.regressionFit.predicted} y={s.regressionFit.actual} note={`R² = ${num(m.r2)}`} />
            <div className="caption">Each dot = one trading day (model-predicted vs actual daily return, %). The tighter
              the cloud hugs y=x, the more the factors explain (higher R²).</div>
            <table className="sc" style={{ marginTop: 10 }}>
              <thead><tr><th>factor</th><th>β (partial)</th><th>p-value</th></tr></thead>
              <tbody>{Object.keys(s.betas).map((f) => (
                <tr key={f}><td>{f}</td><td className="mono">{num(s.betas[f])}</td><td className="mono">{num(s.pvalues[f], 3)}</td></tr>
              ))}</tbody>
            </table>
            <div className="caption">These are <b>partial</b> betas (each factor holding the others fixed) — the
              multivariate coefficients used inside the driver split, <b>not</b> the plain market beta shown up top.</div>
          </div>
        )}
        {tab === 'attr' && (
          <div style={{ marginTop: 14 }}><AttributionTable attr={s.attribution} rawCompounded={m.raw12m} /></div>
        )}
      </div>
    </details>
  );
}

// ---------- the full top-down report for one ticker ----------
function StockReport({ s, config, gate, geminiAvailable, driversCaveat }) {
  const [expl, setExpl] = useState('');
  const [explLoading, setExplLoading] = useState(false);
  const m = s.metrics;
  const fund = gate?.fundamentals;
  const size = gate?.size;

  async function explain() {
    setExplLoading(true);
    try { const r = await explainStock({ ticker: s.ticker, factorSet: config.factorSet, horizon: config.horizon }); setExpl(r.text); }
    catch (e) { setExpl(`⚠️ ${e.message || e}`); }
    finally { setExplLoading(false); }
  }

  return (
    <div>
      {/* header band */}
      <div className="rephead">
        <div className="id">
          <div className="tk">{s.ticker}</div>
          <div className="pills">
            <span className={`pill ${verdictOf(s.trackShort) || 'neutral'}`}>{s.track}</span>
            <span className={`pill ${alphaClass(m)}`}>{alphaLabel(m)}</span>
          </div>
          <div className="vline">{s.verdictLine}</div>
        </div>
        <div className="hstats">
          <div className="hstat"><div className="lbl">Market cap</div><div className="v">{money(size?.marketCap)}</div></div>
          <div className="hstat" title="Plain 1-year market beta (cov/var) — how much it moves with the market. NOT the partial beta used inside the driver split.">
            <div className="lbl">Beta (1y)</div><div className="v">{num(m.marketBeta)}</div></div>
          <div className="hstat"><div className="lbl">Idiosyncratic α+ε</div>
            <div className={`v ${m.idioEndpoint >= 0 ? 'pos' : 'neg'}`}>{pct(m.idioEndpoint)}</div></div>
        </div>
      </div>

      {/* ① Performance Drivers — the flagship */}
      <Section n="①" title="Performance Drivers" tag={<span className="pill neutral">what's moving the stock</span>}
        sub="Where this stock's day-to-day return actually comes from — and how much is its own story vs the market/sector/style/macro tide.">
        <DriversPanel s={s} driversCaveat={driversCaveat} />
      </Section>

      {/* ② Size & Risk */}
      <Section n="②" title="Size & Risk"
        sub="Is it big enough to hold, and how bumpy is the ride?">
        <div className="metrics" style={{ gridTemplateColumns: 'repeat(4, 1fr)', margin: '4px 0 0' }}>
          <div className="metric" title="Live market capitalisation (yfinance).">
            <div className="lbl">Market cap</div><div className="v num">{money(size?.marketCap)}</div>
            <div style={{ marginTop: 6 }}>{size ? <span className={`pill ${size.passed ? 'pass' : 'fail'}`}>{size.passed ? '≥ floor' : 'below floor'}</span> : <span className="pill neutral">n/a</span>}</div>
          </div>
          <div className="metric" title="Annualized volatility of the stock's own daily returns (std × √252) — total risk.">
            <div className="lbl">Volatility (ann.)</div><div className="v num">{pctPlain(m.annualizedVol)}</div>
          </div>
          <div className="metric" title="Plain 1-year market beta (cov/var). NOT the partial beta inside the driver split.">
            <div className="lbl">Market beta (1y)</div><div className="v num">{num(m.marketBeta)}</div>
          </div>
          <div className="metric" title="Worst peak-to-trough decline over the window.">
            <div className="lbl">Max drawdown (1y)</div><div className="v num">{pct(m.maxDrawdown)}</div>
          </div>
        </div>
      </Section>

      {/* ③ Financials */}
      <Section n="③" title="Financials"
        tag={fund && <span className={`pill ${STATUS_PILL[fund.overall] || 'neutral'}`}>{fund.overall}</span>}
        sub={fund?.basis ? `Basis: ${fund.basis} · from SEC filings (never fabricated — unpullable fields marked unverified).`
          : 'From SEC filings (never fabricated — unpullable fields marked unverified).'}>
        {fund ? (
          <div>
            {Object.entries(fund.metrics).map(([k, mv]) => (
              <div className="frow" key={k}>
                <div className="fk">{FUND_LABEL[k] || k.replace(/_/g, ' ')}</div>
                <div className="fnote">{mv.note}</div>
                <div className="fstat"><span className={`pill ${STATUS_PILL[mv.status] || 'neutral'}`}>{mv.status}</span></div>
              </div>
            ))}
          </div>
        ) : <div className="caption">No fundamentals available for {s.ticker}.</div>}
      </Section>

      {/* ④ AI exposure */}
      <Section n="④" title="AI Exposure"
        sub="Filing-sourced confirmation of genuine AI / data-center demand — text only, every claim linked. Confirms, never invents numbers.">
        <ExposureFlow ticker={s.ticker} config={config} geminiAvailable={geminiAvailable} />
      </Section>

      <Diagnostics s={s} config={config} />

      <div style={{ marginTop: 18 }}>
        <button className="btn ghost" onClick={explain} disabled={explLoading || !geminiAvailable}>
          {explLoading ? 'Asking Gemini…' : `🧠 How to read ${s.ticker} (ask Gemini)`}
        </button>
        {expl && <div className="callout" style={{ marginTop: 10, background: 'var(--accent-weak)', color: 'var(--ink)' }}>{expl}</div>}
      </div>
    </div>
  );
}

export default function Results({ data, geminiAvailable }) {
  const [sel, setSel] = useState(data.stocks[0]?.ticker);
  const selected = data.stocks.find((s) => s.ticker === sel) || data.stocks[0];

  return (
    <>
      <div className="eyebrow">Ranked screen · {data.stocks.length} names</div>
      <Summary stocks={data.stocks} gates={data.gates} sel={selected?.ticker} onSelect={setSel} />
      <div className="caption">Ranked by <b>information ratio</b> (own-story alpha per unit of idiosyncratic risk).
        Confidence: <b>Real</b> · <b>Not proven</b> · <b>Likely luck</b>. Click a name to open its full report. New here? See the <b>Glossary</b> tab.</div>
      {data.skipped.length > 0 && (
        <div className="caption">Skipped: {data.skipped.map((x) => `${x.ticker} (${x.reason})`).join('; ')}</div>
      )}
      {data.caveats.droppedFactors && data.caveats.droppedFactors.length > 0 && (
        <div className="caption">Factors dropped (no data): {data.caveats.droppedFactors.join(', ')}</div>
      )}

      {selected && (
        <StockReport key={selected.ticker} s={selected} config={data.config}
          gate={data.gates[selected.ticker]} geminiAvailable={geminiAvailable}
          driversCaveat={data.caveats.driversModeCaveat} />
      )}
    </>
  );
}
