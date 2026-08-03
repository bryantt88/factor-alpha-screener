'use client';
import { useEffect, useState } from 'react';
import { runScreen, listHistory, openRun, health } from '@/lib/api';
import Results from '@/components/Results';
import Glossary from '@/components/Glossary';

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
  const [factorSet, setFactorSet] = useState('drivers');
  const [horizon, setHorizon] = useState(252);
  const [equipment, setEquipment] = useState('');
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [data, setData] = useState(null);
  const [saved, setSaved] = useState(false);
  const [hist, setHist] = useState([]);
  const [gemini, setGemini] = useState(false);

  async function doRun() {
    setBusy(true); setErr(''); setSaved(false);
    try {
      const body = {
        tickers: tickers.split(/[\s,]+/).filter(Boolean),
        factorSet, horizon: Number(horizon),
        equipment: equipment.split(/[\s,]+/).filter(Boolean),
        name, save: false,
      };
      const d = await runScreen(body);
      setData(d); setPage('results');
    } catch (e) { setErr(String(e.message || e)); }
    finally { setBusy(false); }
  }

  async function doSave() {
    setBusy(true);
    try {
      const body = {
        tickers: data.config.tickers, factorSet: data.config.factorSet,
        horizon: data.config.horizon, equipment: data.config.equipmentTickers,
        name: name || data.name, save: true,
      };
      await runScreen(body); setSaved(true);
    } catch (e) { setErr(String(e.message || e)); }
    finally { setBusy(false); }
  }

  useEffect(() => { if (page === 'history') listHistory().then(setHist).catch(() => {}); }, [page]);
  useEffect(() => { health().then((h) => setGemini(!!h.geminiAvailable)).catch(() => {}); }, []);

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand"><span className="bolt">⚡</span> AI-Power Screener</div>
        <div className="tagline">Idiosyncratic-alpha screener for AI-power-stack equities</div>
        <nav className="nav">
          {[['new', '① New Run'], ['results', '② Results'], ['history', '③ History'], ['glossary', '④ Glossary']].map(([k, l]) => (
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
                  placeholder="e.g. AI-power core — Jul 2026" />
              </div>
              <div className="row2">
                <div className="field">
                  <label>Factor mode</label>
                  <div className="seg">
                    {['4factor', 'commodity', 'boss', 'drivers'].map((f) => (
                      <button key={f} className={factorSet === f ? 'on' : ''} onClick={() => setFactorSet(f)}>{f}</button>
                    ))}
                  </div>
                </div>
                <div className="field">
                  <label>Horizon (trading days): {horizon}</label>
                  <input type="range" min="63" max="504" step="21" value={horizon}
                    onChange={(e) => setHorizon(e.target.value)} style={{ width: '100%' }} />
                </div>
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
              <Results data={data} geminiAvailable={gemini} />
            </>
          ) : <div className="caption">No run yet — go to ① New Run.</div>
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
              <div className="tablewrap" style={{ marginTop: 8 }}>
                <table className="sc">
                  <thead><tr><th>name</th><th>as-of</th><th>factor</th><th>horizon</th><th>tickers</th><th></th></tr></thead>
                  <tbody>
                    {hist.map((h) => (
                      <tr key={h.runId}>
                        <td>{h.name}</td><td className="mono">{h.asOfDate}</td><td className="mono">{h.factorSet}</td>
                        <td className="mono">{h.horizon}</td><td>{(h.tickers || []).join(' ')}</td>
                        <td>{h.hasFullResult && (
                          <button className="btn ghost" onClick={async () => {
                            try { const d = await openRun(h.runId); setData(d); setSaved(true); setPage('results'); }
                            catch (e) { setErr(String(e.message || e)); }
                          }}>Open →</button>
                        )}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
