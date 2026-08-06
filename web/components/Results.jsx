'use client';
import { useState } from 'react';
import LineChart from './LineChart';
import ScatterChart from './ScatterChart';
import DriversPanel from './Drivers';
import { runExposure, getVerdict, explainStock } from '@/lib/api';
import { pct, pctPts, pctPlain, num, money, verdictOf, alphaClass, alphaLabel } from '@/lib/format';

const C_IDIO = '#14663A', C_RAW = '#8B98A8';
const FCOLOR = { oil: '#8c564b', brent: '#a0522d', gas: '#c26a1b', market: '#1f5c8a', rates: '#6b5b95' };
const OIL_CAVEAT = 'Oil/gas factors use front-month futures (CL=F / NG=F): monthly rolls + a non-synchronous close attenuate the commodity betas, which can push genuine commodity moves into the idiosyncratic (α+ε). Read α+ε alongside R².';
const STATUS_PILL = { pass: 'pass', fail: 'fail', flag: 'flag', unverified: 'neutral', pending: 'neutral' };
const FUND_LABEL = {
  ebitda_margin: 'EBITDA margin (+ YoY)', net_debt_to_ebitda: 'Net debt / EBITDA',
  earnings_surprise: 'EPS surprise', valuation: 'EV / EBITDA',
  revenue: 'Revenue (+ YoY)', net_income: 'Net income (+ YoY)', pe: 'P/E',
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

// Category colour — SAME mapping the Opportunity "per-stock read" uses, so the two views always agree.
const BUCKET_PILL = {
  'Rising on its own': 'pass', 'Lagging its factors': 'flag',
  'Just riding factors': 'fail', 'No clear edge': 'neutral',
};

// ---------- ranked summary (click a row to open its report) ----------
function Summary({ stocks, gates, buckets, sel, onSelect }) {
  return (
    <div className="summary">
      <div className="srow head">
        <div className="s-rank">#</div><div>Ticker</div><div>Read</div>
        <div style={{ textAlign: 'right' }}>Confidence</div>
        <div style={{ textAlign: 'right' }}>Info ratio</div>
        <div style={{ textAlign: 'right' }} title="Full-period own-story (α+ε) return — the basis for the Read">Own-story</div>
        <div style={{ textAlign: 'right' }}>Mkt cap</div>
      </div>
      {stocks.map((s, i) => {
        const bucket = buckets[s.ticker] || s.trackShort;   // same category as the per-stock read
        const v = BUCKET_PILL[bucket] || 'neutral';
        const mc = gates[s.ticker]?.size?.marketCap;
        return (
          <div key={s.ticker} className={`srow ${sel === s.ticker ? 'sel' : ''}`} onClick={() => onSelect(s.ticker)}>
            <div className="s-rank">{i + 1}</div>
            <div className="s-tk">{s.ticker}</div>
            <div className="s-verdict"><span className={`s-dot ${v}`} />{bucket}</div>
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
  const [grade, setGrade] = useState('');           // final grade (AI's, or overridden)
  const [verdict, setVerdict] = useState(null);
  const [err, setErr] = useState('');

  async function run(deep) {
    setLoading(deep ? 'web' : 'news'); setErr(''); setVerdict(null);
    try {
      const p = await runExposure(ticker, deep);
      setProp(p); setGrade(p.grade);
    } catch (e) { setErr(String(e.message || e)); }
    finally { setLoading(''); }
  }
  async function decide(d) {
    try {
      const v = await getVerdict({ grade, type: prop.type, error: prop.error, decision: d });
      setVerdict(v);
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

          <div className="field" style={{ maxWidth: 260, marginTop: 8 }}>
            <label>Final grade (you decide — overrides the AI)</label>
            <select className="select" value={grade} onChange={(e) => setGrade(e.target.value)}>
              {grades.map((g) => <option key={g} value={g}>{GRADE_LABEL[g] || g}</option>)}
            </select>
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
            <div className="callout" style={{ marginTop: 8 }}>⚠ These <b>partial</b> betas are a <b>calculation input, not a readable exposure.</b> When
              factors overlap (especially the style ETFs), a beta can inflate or flip sign — a stock can show β −2.5 on low-vol while
              its actual <i>correlation</i> with low-vol is ~0. To read how the stock relates to a factor, use the <b>correlation</b> in
              the factor table above; for what drives its risk, use the grouped <b>variance shares</b> (collinearity-robust). The plain
              market beta shown up top is also a simple univariate beta, not one of these partials.</div>
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
function StockReport({ s, config, gate, geminiAvailable, driversCaveat, bucket, readNote }) {
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
            <span className={`pill ${BUCKET_PILL[bucket] || 'neutral'}`}>{bucket || s.trackShort}</span>
            <span className={`pill ${alphaClass(m)}`}>{alphaLabel(m)}</span>
          </div>
          <div className="vline">{readNote || s.verdictLine}</div>
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
        sub={`${fund?.basis ? `Basis: ${fund.basis} · ` : ''}from SEC filings${fund?.industry ? ` · multiples vs ${fund.industry.name} avg (${fund.industry.source})` : ''}. Never fabricated — unpullable fields marked unverified.`}>
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
  const readByTicker = Object.fromEntries((data.opportunity?.reads || []).map((r) => [r.ticker, r]));
  const selRead = selected ? readByTicker[selected.ticker] : null;

  return (
    <>
      <div className="eyebrow">Ranked screen · {data.stocks.length} names</div>
      <Summary stocks={data.stocks} gates={data.gates}
        buckets={Object.fromEntries(Object.entries(readByTicker).map(([k, r]) => [k, r.bucket]))}
        sel={selected?.ticker} onSelect={setSel} />
      <div className="caption">This is the <b>per-stock read for every name</b> — ranked by <b>information ratio</b>, best first.
        (The <b>Trade ideas</b> panel above is just the actionable shortlist drawn from these.) Click a name to open its full report.</div>
      <details className="diag" style={{ marginTop: 6 }}>
        <summary>How is this sorted & categorised? (click to expand)</summary>
        <div className="diagbody" style={{ fontSize: 13, lineHeight: 1.6 }}>
          <p><b>Sorted by — Information Ratio (IR):</b> own-story return per unit of own-story risk (annualised α ÷ idiosyncratic vol).
            Higher = a steadier, higher-quality own-story trend. Ties sink to the bottom if IR can't be computed.</p>
          <p><b>Read (category) — decided over the FULL period</b> by two things: the sign of the <i>own-story</i> return (α+ε, after
            stripping market/sector/commodity) and whether that α is <i>statistically real</i> (its t-stat):</p>
          <ul style={{ margin: '4px 0' }}>
            <li><span className="pill pass">Rising on its own</span> — own-story <b>up</b> AND real (t ≥ 2). A candidate long.</li>
            <li><span className="pill fail">Just riding factors</span> — own-story up, but <b>not</b> statistically real (t &lt; 2) — the gain is mostly the market/sector/commodity, not the stock. Fade.</li>
            <li><span className="pill flag">Lagging its factors</span> — own-story <b>down</b> while the stock has real factor exposure — a possible mean-reversion bounce.</li>
            <li><span className="pill neutral">No clear edge</span> — own-story flat; the move is basically factor beta.</li>
          </ul>
          <p><b>Confidence</b> is the same t-stat, named: <b>Real</b> (t ≥ 2) · <b>Not proven</b> (t 1–2) · <b>Likely luck</b> (t &lt; 1).
            So a name can be “Just riding factors” yet still show “Not proven” — it’s up, just not <i>provably</i> on its own.</p>
          <p className="caption" style={{ margin: 0 }}>⏱ The Read judges the <b>whole period</b>. A name can be “Rising on its own” over the year and still be
            <b> down recently</b> — e.g. Own-story +1065% for the year but −24% in the last quarter. That's a normal pullback in a strong
            uptrend, not a contradiction; the recent move shows as a <b>recent ▲/▼</b> tag on its trade card.</p>
        </div>
      </details>
      {data.skipped.length > 0 && (
        <div className="caption">Skipped: {data.skipped.map((x) => `${x.ticker} (${x.reason})`).join('; ')}</div>
      )}
      {data.caveats.droppedFactors && data.caveats.droppedFactors.length > 0 && (
        <div className="caption">Factors dropped (no data): {data.caveats.droppedFactors.join(', ')}</div>
      )}

      {selected && (
        <StockReport key={selected.ticker} s={selected} config={data.config}
          gate={data.gates[selected.ticker]} geminiAvailable={geminiAvailable}
          driversCaveat={data.caveats.driversModeCaveat}
          bucket={selRead?.bucket} readNote={selRead?.note} />
      )}
    </>
  );
}
