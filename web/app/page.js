'use client';
import { useEffect, useState } from 'react';
import { runScreen, listHistory, openRun, health, listBacktests, openBacktest,
  deleteRun, clearHistory, deleteBacktest, clearBacktests } from '@/lib/api';
import Results from '@/components/Results';
import Opportunity from '@/components/Opportunity';
import DriverBuilder from '@/components/DriverBuilder';
import Backtest from '@/components/Backtest';
import Glossary from '@/components/Glossary';

// Market / factor presets. US modes use a named factor set; region/custom modes send an explicit
// driver list (region-agnostic). Indonesia proxies are all yfinance-verified (^JKSE / IDR=X / BZ=F).
const PRESETS = {
  us_drivers: { label: 'US · full factors', mode: 'drivers', drivers: null },
  us_commodity: { label: 'commodity drivers', mode: 'custom', drivers: [
    { name: 'oil', ticker: 'CL=F', group: 'Energy' },
    { name: 'gas', ticker: 'NG=F', group: 'Energy' },
    { name: 'gold', ticker: 'GC=F', group: 'Metals' },
  ] },
  indonesia: { label: 'Indonesia', mode: 'custom', drivers: [
    { name: 'market', ticker: '^JKSE', group: 'Market' },
    { name: 'fx', ticker: 'IDR=X', group: 'FX' },
    { name: 'oil', ticker: 'BZ=F', group: 'Energy' },
  ] },
  custom: { label: 'Custom', mode: 'custom', drivers: [] },
};

function Hero({ title, sub }) {
  return (
    <div className="hero">
      <div className="row"><span className="mark">⚡</span><h1>{title}</h1></div>
      <div className="sub" dangerouslySetInnerHTML={{ __html: sub }} />
      <div className="rule" />
    </div>
  );
}

export default function Home() {
  const [page, setPage] = useState('new');
  const [tickers, setTickers] = useState('CEG VST NRG VRT ETN');
  const [preset, setPreset] = useState('us_drivers');
  const [drivers, setDrivers] = useState([]);   // active only for region/custom presets
  const [horizon, setHorizon] = useState(252);           // risk window (betas / hedge)
  const [signalHorizon, setSignalHorizon] = useState(63); // signal window (fast timing)
  const [equipment, setEquipment] = useState('');
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [data, setData] = useState(null);
  const [saved, setSaved] = useState(false);
  const [hist, setHist] = useState([]);
  const [btList, setBtList] = useState([]);
  const [loadedBt, setLoadedBt] = useState(null);
  const [btKey, setBtKey] = useState(0);
  const [gemini, setGemini] = useState(false);

  function choosePreset(k) {
    setPreset(k);
    const pr = PRESETS[k];
    if (pr.drivers && pr.drivers.length) setDrivers(pr.drivers.map((d) => ({ ...d })));
  }

  async function doRun() {
    setBusy(true); setErr(''); setSaved(false);
    try {
      const pr = PRESETS[preset];
      const usesCustom = pr.mode === 'custom';
      const cleanDrivers = drivers
        .map((d) => ({ name: d.name.trim(), ticker: d.ticker.trim(), group: (d.group || '').trim() }))
        .filter((d) => d.name && d.ticker);
      if (usesCustom && cleanDrivers.length === 0) {
        setErr('Add at least one driver (name + ticker) for a custom / region screen.');
        setBusy(false); return;
      }
      const body = {
        tickers: tickers.split(/[\s,]+/).filter(Boolean),
        factorSet: usesCustom ? 'custom' : pr.mode,
        horizon: Number(horizon), signalHorizon: Number(signalHorizon),
        equipment: equipment.split(/[\s,]+/).filter(Boolean),
        name, save: false,
        ...(usesCustom ? { drivers: cleanDrivers } : {}),
      };
      const d = await runScreen(body);
      setData(d); setPage('results');
    } catch (e) { setErr(String(e.message || e)); }
    finally { setBusy(false); }
  }

  async function doSave() {
    setBusy(true);
    try {
      const cd = data.config.customDrivers;   // present iff the run used a custom driver set
      const body = {
        tickers: data.config.tickers, factorSet: data.config.factorSet,
        horizon: data.config.horizon, equipment: data.config.equipmentTickers,
        name: name || data.name, save: true,
        ...(cd ? { drivers: cd } : {}),
      };
      await runScreen(body); setSaved(true);
    } catch (e) { setErr(String(e.message || e)); }
    finally { setBusy(false); }
  }

  function refreshHistory() {
    listHistory().then(setHist).catch(() => {});
    listBacktests().then(setBtList).catch(() => {});
  }
  useEffect(() => { if (page === 'history') refreshHistory(); }, [page]);

  async function doDeleteRun(runId, label) {
    if (!window.confirm(`Delete saved run “${label}”? This can’t be undone.`)) return;
    try { await deleteRun(runId); refreshHistory(); }
    catch (e) { setErr(String(e.message || e)); }
  }
  async function doClearHistory() {
    if (!window.confirm(`Delete ALL ${hist.length} saved run(s)? This can’t be undone.`)) return;
    try { await clearHistory(); setHist([]); }
    catch (e) { setErr(String(e.message || e)); }
  }
  async function doDeleteBacktest(id, label) {
    if (!window.confirm(`Delete saved backtest “${label}”? This can’t be undone.`)) return;
    try { await deleteBacktest(id); refreshHistory(); }
    catch (e) { setErr(String(e.message || e)); }
  }
  async function doClearBacktests() {
    if (!window.confirm(`Delete ALL ${btList.length} saved backtest(s)? This can’t be undone.`)) return;
    try { await clearBacktests(); setBtList([]); }
    catch (e) { setErr(String(e.message || e)); }
  }

  async function openSavedBacktest(id) {
    try { const p = await openBacktest(id); setLoadedBt(p); setBtKey((k) => k + 1); setPage('backtest'); }
    catch (e) { setErr(String(e.message || e)); }
  }
  useEffect(() => { health().then((h) => setGemini(!!h.geminiAvailable)).catch(() => {}); }, []);

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand"><span className="bolt">⚡</span> Factor-Alpha Screener</div>
        <div className="tagline">Idiosyncratic-alpha & market-neutral trade ideas — any market, any drivers</div>
        <nav className="nav">
          {[['new', '① New Run'], ['results', '② Results'], ['backtest', '③ Backtest'], ['history', '④ History'], ['glossary', '⑤ Glossary']].map(([k, l]) => (
            <button key={k} className={page === k ? 'active' : ''} onClick={() => setPage(k)}>{l}</button>
          ))}
        </nav>
        <div className="status">Performance-driver screen. Ranked by information ratio; verdict colour = meaning.<br /><br />
          {gemini ? '🟢 Gemini CLI detected — AI-exposure + explainer live' : '⚪ Gemini CLI not found — AI-exposure disabled'}</div>
      </aside>

      <main className="main">
        {err && <div className="err" style={{ marginBottom: 16 }}>{err}</div>}

        {page === 'new' && (
          <>
            <Hero title="New run" sub="Paste tickers, choose the factor mode, and run. Every ticker is scored — nothing is dropped." />
            <div className="card" style={{ marginTop: 8 }}>
              <div className="field">
                <label>Tickers</label>
                <input className="input" value={tickers} onChange={(e) => setTickers(e.target.value)} />
              </div>
              <div className="field">
                <label>Run name (optional)</label>
                <input className="input" value={name} onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. US power core — Jul 2026" />
              </div>
              <div className="field">
                <label>Market / factor preset</label>
                <div className="seg">
                  {Object.entries(PRESETS).map(([k, p]) => (
                    <button key={k} className={preset === k ? 'on' : ''} onClick={() => choosePreset(k)}>{p.label}</button>
                  ))}
                </div>
              </div>
              {PRESETS[preset].mode === 'custom' && (
                <DriverBuilder drivers={drivers} setDrivers={setDrivers}
                  region={preset === 'indonesia' ? 'indonesia' : 'us'} />
              )}
              <div className="row2">
                <div className="field">
                  <label>Risk window — betas / hedge (days): {horizon}</label>
                  <input type="range" min="126" max="504" step="21" value={horizon}
                    onChange={(e) => setHorizon(e.target.value)} style={{ width: '100%' }} />
                </div>
                <div className="field">
                  <label>Signal window — recent timing (days): {signalHorizon}</label>
                  <input type="range" min="21" max="189" step="21" value={signalHorizon}
                    onChange={(e) => setSignalHorizon(e.target.value)} style={{ width: '100%' }} />
                </div>
              </div>
              <div className="caption" style={{ marginTop: -2 }}>
                Betas (the hedge) come from the <b>risk window</b> so they stay stable; the <b>signal window</b> reads the
                recent idiosyncratic trajectory, so a shorter one surfaces fresher entries/exits.
              </div>
              <div className="field">
                <label>Equipment names (fundamentals only — no regression)</label>
                <input className="input" value={equipment} onChange={(e) => setEquipment(e.target.value)}
                  placeholder="e.g. ETN VRT" />
              </div>
              <button className="btn" onClick={doRun} disabled={busy}>
                {busy ? 'Running…' : 'Run screen'}
              </button>
              {busy && <div className="spinner" style={{ marginTop: 10 }}>Pulling prices and running the regression…</div>}
            </div>
          </>
        )}

        {page === 'results' && (
          data ? (
            <>
              <Hero title="Results"
                sub={`as-of ${data.config.asOfDate} · factor set <b>${data.config.factorSet}</b> · horizon ${data.config.horizon}d · ${data.stocks.length} scored`} />
              <div className="card" style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 8 }}>
                {saved ? <span className="pill pass">✓ Saved to knowledge base</span> : (
                  <>
                    <input className="input" style={{ maxWidth: 320 }} value={name}
                      onChange={(e) => setName(e.target.value)} placeholder="Name this run (optional)" />
                    <button className="btn" onClick={doSave} disabled={busy}>💾 Add to Knowledge Base</button>
                    <span className="caption" style={{ margin: 0 }}>Nothing is saved until you add it.</span>
                  </>
                )}
              </div>
              {data.dropped && data.dropped.length > 0 && (
                <div className="caption">Excluded (existing position / not covered): {data.dropped.join(', ')}</div>
              )}
              <Opportunity data={data} />
              <Results data={data} geminiAvailable={gemini} />
            </>
          ) : <div className="caption">No run yet — go to ① New Run.</div>
        )}

        {page === 'backtest' && (
          <>
            <Hero title="Backtest — market-neutral book" sub="A standalone lab: pick a <b>universe</b> and the <b>drivers</b> to hedge against, choose a strategy preset, and walk it forward. Long the qualifying names, short factor proxies to zero the market beta — net of costs. Self-contained (nothing here comes from ① New Run)." />
            <Backtest presets={PRESETS} initialResult={loadedBt} key={btKey} />
          </>
        )}

        {page === 'glossary' && (
          <>
            <Hero title="Glossary" sub="Every term, metric, and chart line explained — plain-language, for a portfolio manager." />
            <Glossary />
          </>
        )}

        {page === 'history' && (
          <>
            <Hero title="History / knowledge base" sub="Only runs you add are kept — each re-opens the full report." />
            {data && data.runId && saved && <div className="caption">Tip: open your saved run below.</div>}
            {hist.length === 0 ? <div className="caption">No saved runs yet.</div> : (
              <>
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 8 }}>
                  <button className="btn ghost danger sm" onClick={doClearHistory}>🗑 Clear all runs</button>
                </div>
                <div className="tablewrap" style={{ marginTop: 8 }}>
                  <table className="sc">
                    <thead><tr><th>name</th><th>as-of</th><th>factor</th><th>horizon</th><th>tickers</th><th style={{ textAlign: 'right' }}>actions</th></tr></thead>
                    <tbody>
                      {hist.map((h) => (
                        <tr key={h.runId}>
                          <td>{h.name}</td><td className="mono">{h.asOfDate}</td><td className="mono">{h.factorSet}</td>
                          <td className="mono">{h.horizon}</td><td>{(h.tickers || []).join(' ')}</td>
                          <td>
                            <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                              {h.hasFullResult && (
                                <button className="btn ghost sm" onClick={async () => {
                                  try { const d = await openRun(h.runId); setData(d); setSaved(true); setPage('results'); }
                                  catch (e) { setErr(String(e.message || e)); }
                                }}>Open →</button>
                              )}
                              <button className="btn ghost danger sm" onClick={() => doDeleteRun(h.runId, h.name)}>Delete</button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}

            <div className="eyebrow" style={{ marginTop: 22 }}>Saved backtests</div>
            {btList.length === 0 ? <div className="caption">No saved backtests yet — run one on ③ Backtest and click “Add to Knowledge Base”.</div> : (
              <>
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 8 }}>
                  <button className="btn ghost danger sm" onClick={doClearBacktests}>🗑 Clear all backtests</button>
                </div>
                <div className="tablewrap" style={{ marginTop: 8 }}>
                  <table className="sc">
                    <thead><tr><th>name</th><th>saved</th><th>universe</th><th style={{ textAlign: 'right' }}>CAGR</th>
                      <th style={{ textAlign: 'right' }}>vol</th><th style={{ textAlign: 'right' }}>maxDD</th>
                      <th style={{ textAlign: 'right' }}>Sharpe</th><th style={{ textAlign: 'right' }}>beta</th><th style={{ textAlign: 'right' }}>actions</th></tr></thead>
                    <tbody>
                      {btList.map((b) => {
                        const s = b.summary || {};
                        const f = (x, d = 0) => (x == null ? '—' : (x * (d ? 1 : 100)).toFixed(d ? 2 : 0) + (d ? '' : '%'));
                        return (
                          <tr key={b.id}>
                            <td>{b.name}</td>
                            <td className="mono">{(b.timestamp || '').slice(0, 10)}</td>
                            <td className="mono">{(b.stocks || []).length} names</td>
                            <td className="mono" style={{ textAlign: 'right' }}>{f(s.cagr)}</td>
                            <td className="mono" style={{ textAlign: 'right' }}>{f(s.annVol)}</td>
                            <td className="mono" style={{ textAlign: 'right' }}>{f(s.maxDrawdown)}</td>
                            <td className="mono" style={{ textAlign: 'right' }}>{f(s.sharpe, 2)}</td>
                            <td className="mono" style={{ textAlign: 'right' }}>{f(s.realizedMarketBeta, 2)}</td>
                            <td>
                              <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                                <button className="btn ghost sm" onClick={() => openSavedBacktest(b.id)}>Open →</button>
                                <button className="btn ghost danger sm" onClick={() => doDeleteBacktest(b.id, b.name)}>Delete</button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </>
        )}
      </main>
    </div>
  );
}
