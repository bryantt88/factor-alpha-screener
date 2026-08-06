'use client';
// Backtest — a STANDALONE tool: its own universe + its own drivers, independent of the New Run tab.
// Walk-forward test of the market-neutral book (long the qualifying names, short factor proxies to
// zero net beta). Built-in universe presets, one-click strategy presets (incl. the saved low-vol
// neutral config), equity + drawdown charts, all thresholds tunable. No look-ahead.
import { useState } from 'react';
import LineChart from './LineChart';
import DriverBuilder from './DriverBuilder';
import { runBacktest, saveBacktest } from '@/lib/api';
import { pct, num } from '@/lib/format';

const REBAL = [['21', 'Monthly'], ['10', 'Fortnightly'], ['5', 'Weekly'], ['63', 'Quarterly']];
const SPAN = [['252', '1y'], ['504', '2y'], ['756', '3y'], ['1260', '5y']];
const C_NEUTRAL = '#14663A', C_LONG = '#8B98A8', C_BASKET = '#1f5c8a', C_MKT = '#c9a227';

// Built-in universes (paste-free). US-100 = broad, deep, 5y+ history — the pool the neutral book needs.
const US100 = 'AAPL MSFT NVDA AVGO ORCL CRM ADBE CSCO ACN AMD QCOM TXN IBM NOW INTU GOOGL META NFLX DIS CMCSA TMUS AMZN TSLA HD MCD NKE SBUX LOW TJX BKNG CMG WMT COST PG KO PEP PM MO CL LLY UNH JNJ ABBV MRK PFE TMO ABT DHR AMGN ISRG JPM BAC WFC GS MS AXP BLK SPGI C SCHW GE CAT HON UNP DE LMT RTX UPS XOM CVX COP LIN NEE DUK V MA PYPL AMAT MU ADI LRCX PANW BMY GILD MDT CVS CI ELV SO D AEP EMR ETN ITW PH GD NOC FDX GM TGT MDLZ KHC MNST MAR CHTR VZ';
const UNIVERSES = {
  us100: { label: 'US Large-Cap 100', tickers: US100 },
  aipower: { label: 'AI-Power', tickers: 'CEG VST NRG VRT ETN POWL PWR TLN NEE GE' },
  custom: { label: 'Custom', tickers: '' },
};

// One-click strategy presets. 'lowvol' = the saved out-of-sample-validated low-vol neutral book.
const STRATS = {
  lowvol: { label: 'Low-vol neutral ✦', minTstat: 0.5, minLongs: 10, maxLongs: 0, useSignalGate: false, rebalance: '21' },
  balanced: { label: 'Balanced return', minTstat: 0.75, minLongs: 5, maxLongs: 20, useSignalGate: false, rebalance: '21' },
  strict: { label: 'Strict (real alpha)', minTstat: 2.0, minLongs: 3, maxLongs: 0, useSignalGate: true, rebalance: '21' },
  custom: { label: 'Custom' },
};

function Stat({ label, value, hint }) {
  return <div className="metric" title={hint || ''}><div className="lbl">{label}</div><div className="v num">{value}</div></div>;
}
const underwater = (eq) => { let pk = eq.length ? eq[0] : 1; return eq.map((v) => { pk = Math.max(pk, v); return (v / pk - 1) * 100; }); };

export default function Backtest({ presets, initialResult }) {
  const [uniKey, setUniKey] = useState('us100');
  const [universe, setUniverse] = useState(UNIVERSES.us100.tickers);
  const [preset, setPreset] = useState('us_4factor');   // factor model (4factor = clean hedge basis)
  const [drivers, setDrivers] = useState([]);
  const [horizon, setHorizon] = useState(252);
  const [signalHorizon, setSignalHorizon] = useState(63);
  const [stratKey, setStratKey] = useState('lowvol');
  const [rebalance, setRebalance] = useState('21');
  const [testDays, setTestDays] = useState('756');
  const [minLongs, setMinLongs] = useState(10);
  const [maxLongs, setMaxLongs] = useState(0);
  const [minTstat, setMinTstat] = useState(0.5);
  const [useSignalGate, setUseSignalGate] = useState(false);
  const [costBps, setCostBps] = useState(10);
  const [borrowBps, setBorrowBps] = useState(50);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [res, setRes] = useState(initialResult || null);
  const [saveName, setSaveName] = useState('');
  const [saved, setSaved] = useState(false);

  function chooseUniverse(k) { setUniKey(k); if (UNIVERSES[k].tickers) setUniverse(UNIVERSES[k].tickers); }
  function choosePreset(k) { setPreset(k); const pr = presets[k]; if (pr.drivers && pr.drivers.length) setDrivers(pr.drivers.map((d) => ({ ...d }))); }
  function chooseStrat(k) {
    setStratKey(k); const s = STRATS[k];
    if (s.minTstat !== undefined) {
      setMinTstat(s.minTstat); setMinLongs(s.minLongs); setMaxLongs(s.maxLongs);
      setUseSignalGate(s.useSignalGate); setRebalance(s.rebalance);
    }
  }

  async function doSave() {
    try { await saveBacktest(res, saveName); setSaved(true); }
    catch (e) { setErr(String(e.message || e)); }
  }

  async function run() {
    setBusy(true); setErr(''); setRes(null); setSaved(false);
    try {
      const pr = presets[preset];
      const usesCustom = pr.mode === 'custom';
      const cleanDrivers = drivers.map((d) => ({ name: d.name.trim(), ticker: d.ticker.trim(), group: (d.group || '').trim() })).filter((d) => d.name && d.ticker);
      if (usesCustom && cleanDrivers.length === 0) { setErr('Add at least one driver.'); setBusy(false); return; }
      const tickers = universe.split(/[\s,]+/).filter(Boolean);
      if (tickers.length < 5) { setErr('Give at least ~5 tickers (a market-neutral book needs a pool to pick from).'); setBusy(false); return; }
      const body = {
        tickers, factorSet: usesCustom ? 'custom' : pr.mode,
        horizon: Number(horizon), signalHorizon: Number(signalHorizon),
        rebalance: Number(rebalance), costBps: Number(costBps), testDays: Number(testDays),
        minLongs: Number(minLongs), maxLongs: Number(maxLongs), minTstat: Number(minTstat),
        useSignalGate, borrowBps: Number(borrowBps),
        ...(usesCustom ? { drivers: cleanDrivers } : {}),
      };
      setRes(await runBacktest(body));
    } catch (e) { setErr(String(e.message || e)); }
    finally { setBusy(false); }
  }

  const n = res && res.neutral, st = res && res.stats;
  return (
    <>
      <div className="card">
        {/* Universe */}
        <div className="field">
          <label>Universe — the names to pick from</label>
          <div className="seg" style={{ marginBottom: 8 }}>
            {Object.entries(UNIVERSES).map(([k, u]) => (
              <button key={k} className={uniKey === k ? 'on' : ''} onClick={() => chooseUniverse(k)}>{u.label}</button>
            ))}
          </div>
          <textarea className="input" rows={2} value={universe} onChange={(e) => { setUniverse(e.target.value); setUniKey('custom'); }}
            style={{ resize: 'vertical', fontFamily: 'var(--mono, monospace)', fontSize: 12 }} />
          <div className="caption" style={{ marginTop: 4 }}>{universe.split(/[\s,]+/).filter(Boolean).length} tickers. A neutral book wants a deep pool — more names = smoother.</div>
        </div>

        {/* Drivers */}
        <div className="field">
          <label>Drivers — the factor model to hedge against</label>
          <div className="seg">
            {Object.entries(presets).map(([k, p]) => (
              <button key={k} className={preset === k ? 'on' : ''} onClick={() => choosePreset(k)}>{p.label}</button>
            ))}
          </div>
        </div>
        {presets[preset].mode === 'custom' && (
          <DriverBuilder drivers={drivers} setDrivers={setDrivers} region={preset === 'indonesia' ? 'indonesia' : 'us'} />
        )}

        {/* Strategy preset */}
        <div className="field">
          <label>Strategy preset</label>
          <div className="seg">
            {Object.entries(STRATS).map(([k, s]) => (
              <button key={k} className={stratKey === k ? 'on' : ''} onClick={() => chooseStrat(k)}>{s.label}</button>
            ))}
          </div>
          <div className="caption" style={{ marginTop: 4 }}>
            <b>Low-vol neutral ✦</b> = the saved config: many names, loose alpha bar, monthly — beta ≈ 0, low drawdown.
          </div>
        </div>

        {/* Knobs */}
        <div className="row2">
          <div className="field">
            <label>Rebalance every</label>
            <div className="seg">{REBAL.map(([k, l]) => <button key={k} className={rebalance === k ? 'on' : ''} onClick={() => { setRebalance(k); setStratKey('custom'); }}>{l}</button>)}</div>
          </div>
          <div className="field">
            <label>Test length</label>
            <div className="seg">{SPAN.map(([k, l]) => <button key={k} className={testDays === k ? 'on' : ''} onClick={() => setTestDays(k)}>{l}</button>)}</div>
          </div>
        </div>
        <div className="row2">
          <div className="field">
            <label>Alpha conviction — min t-stat: {Number(minTstat).toFixed(2)}</label>
            <input type="range" min="0.5" max="2.5" step="0.25" value={minTstat} onChange={(e) => { setMinTstat(e.target.value); setStratKey('custom'); }} style={{ width: '100%' }} />
          </div>
          <div className="field">
            <label>Entry timing filter</label>
            <div className="seg">
              <button className={useSignalGate ? 'on' : ''} onClick={() => { setUseSignalGate(true); setStratKey('custom'); }}>On</button>
              <button className={!useSignalGate ? 'on' : ''} onClick={() => { setUseSignalGate(false); setStratKey('custom'); }}>Off</button>
            </div>
          </div>
        </div>
        <div className="row2">
          <div className="field">
            <label>Min names (else cash): {minLongs}</label>
            <input type="range" min="1" max="20" step="1" value={minLongs} onChange={(e) => { setMinLongs(e.target.value); setStratKey('custom'); }} style={{ width: '100%' }} />
          </div>
          <div className="field">
            <label>Max names held: {Number(maxLongs) === 0 ? 'no cap' : maxLongs}</label>
            <input type="range" min="0" max="40" step="5" value={maxLongs} onChange={(e) => { setMaxLongs(e.target.value); setStratKey('custom'); }} style={{ width: '100%' }} />
          </div>
        </div>
        <div className="row2">
          <div className="field">
            <label>Cost / turnover (bps): {costBps}</label>
            <input type="range" min="0" max="50" step="1" value={costBps} onChange={(e) => setCostBps(e.target.value)} style={{ width: '100%' }} />
          </div>
          <div className="field">
            <label>Short-borrow (bps/yr): {borrowBps}</label>
            <input type="range" min="0" max="300" step="10" value={borrowBps} onChange={(e) => setBorrowBps(e.target.value)} style={{ width: '100%' }} />
          </div>
        </div>
        <button className="btn" onClick={run} disabled={busy}>{busy ? 'Running walk-forward…' : '▶ Run backtest'}</button>
        {busy && <div className="spinner" style={{ marginTop: 10 }}>Pulling history and replaying the signal…</div>}
        {err && <div className="err" style={{ marginTop: 10 }}>{err}</div>}
      </div>

      {res && (
        <>
          <div className="card" style={{ display: 'flex', gap: 12, alignItems: 'center', marginTop: 8, flexWrap: 'wrap' }}>
            {saved ? <span className="pill pass">✓ Saved to knowledge base</span> : (
              <>
                <input className="input" style={{ maxWidth: 320 }} value={saveName}
                  onChange={(e) => setSaveName(e.target.value)} placeholder="Name this backtest (e.g. US-100 low-vol neutral)" />
                <button className="btn" onClick={doSave}>💾 Add to Knowledge Base</button>
                <span className="caption" style={{ margin: 0 }}>Saved backtests re-open from the ④ History tab.</span>
              </>
            )}
          </div>
          <div className="metrics" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginTop: 14 }}>
            <Stat label="Total return" value={pct(n.totalReturn)} hint="Neutral book, net of costs + borrow" />
            <Stat label="Return / yr (CAGR)" value={pct(n.cagr)} />
            <Stat label="Volatility (ann.)" value={pct(n.annVol)} hint="Lower = smoother. Compare to the market line." />
            <Stat label="Max drawdown" value={pct(n.maxDrawdown)} hint="Worst peak-to-trough — the key risk number" />
            <Stat label="Sharpe" value={num(n.sharpe)} />
            <Stat label="Market beta" value={num(st.realizedMarketBeta)} hint="≈0 = genuinely market-neutral" />
            <Stat label="% time invested" value={pct(st.pctInvested)} hint="Rest of the time it sat in cash (too few names qualified)" />
            <Stat label="Avg # longs" value={num(st.avgLongs)} hint="Long this many stocks; short factor ETFs to hedge" />
          </div>

          <div className="card" style={{ marginTop: 14 }}>
            <div className="eyebrow">Growth of the book vs benchmarks (%)</div>
            <LineChart dates={res.dates} series={[
              { name: 'neutral', color: C_NEUTRAL, values: n.equity.map((v) => (v - 1) * 100) },
              { name: 'long-only', color: C_LONG, values: res.longOnly.equity.map((v) => (v - 1) * 100) },
              ...(res.basket ? [{ name: 'buy-hold basket', color: C_BASKET, values: res.basket.equity.map((v) => (v - 1) * 100) }] : []),
              ...(res.market ? [{ name: 'market', color: C_MKT, values: res.market.equity.map((v) => (v - 1) * 100) }] : []),
            ]} />
            <div className="caption" style={{ marginTop: 6 }}>
              <span style={{ color: C_NEUTRAL }}>■</span> neutral · <span style={{ color: C_LONG }}>■</span> long-only ·
              <span style={{ color: C_BASKET }}> ■</span> buy-hold · <span style={{ color: C_MKT }}> ■</span> market.
              Holds ~{Math.round(st.avgLongs)} longs + short factor proxies (SPY / TLT / CL=F / NG=F) to neutralise beta.
            </div>
          </div>

          <div className="card" style={{ marginTop: 14 }}>
            <div className="eyebrow">Drawdown — how deep underwater, and for how long (%)</div>
            <LineChart dates={res.dates} series={[
              { name: 'neutral', color: C_NEUTRAL, values: underwater(n.equity) },
              ...(res.basket ? [{ name: 'buy-hold basket', color: C_BASKET, values: underwater(res.basket.equity) }] : []),
            ]} />
            <div className="caption" style={{ marginTop: 6 }}>
              The shallow green line is the whole point — the neutral book's drawdowns stay small ({pct(n.maxDrawdown)} worst)
              vs holding the stocks ({res.basket ? pct(res.basket.maxDrawdown) : '—'}).
            </div>
          </div>

          <div className="callout" style={{ marginTop: 10 }}>
            <b>Read honestly.</b> A good number on the whole window is <b>in-sample</b> — tune on an early stretch, judge on
            a later one you didn't touch. Costs = turnover × bps + annual borrow (no slippage); universe is today's tickers
            (survivorship). {st.realizedMarketBeta != null && Math.abs(st.realizedMarketBeta) > 0.15 &&
              <>⚠ Realized beta {num(st.realizedMarketBeta)} — not fully neutral. </>}
            {res.missing && res.missing.length > 0 && <>Dropped (no data): {res.missing.join(', ')}.</>}
          </div>
        </>
      )}
    </>
  );
}
