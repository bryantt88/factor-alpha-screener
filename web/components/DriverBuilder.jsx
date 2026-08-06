'use client';
// Custom driver builder — the region-agnostic factor model. The user edits the list of drivers
// (logical name · yfinance ticker · group) this basket is regressed on. Any yfinance ticker works,
// so the same engine serves US (SPY/TLT/CL=F) or Indonesia (^JKSE/IDR=X/BZ=F) or anything else.
// Coal/palm-oil have no free physical future on yfinance, so the quick-adds use LABELLED equity
// proxies (BTU/POAHY) — honest, swappable, never presented as the physical price.

// Region-specific starters, plus shared palettes of yfinance-VERIFIED proxies (all confirmed to pull).
const QUICK = {
  us: [['rates', 'TLT', 'Rates'], ['value', 'IWD', 'Style'], ['growth', 'IWF', 'Style'],
       ['momentum', 'MTUM', 'Style'], ['credit', 'HYG', 'Macro']],
  indonesia: [['em', 'EEM', 'Market'], ['coal', 'BTU', 'Energy (proxy)'],
              ['palm', 'POAHY', 'Agri (proxy)']],
};
// Shared, always-available driver palettes (validated tickers). Kept to the mainstream macro drivers —
// broad metals, energy and FX — no niche softs (coffee/sugar/etc.). Grouped so the variance panel reads well.
const PALETTES = [
  ['Metals', [['gold', 'GC=F'], ['silver', 'SI=F'], ['copper', 'HG=F']]],
  ['Energy', [['oil_wti', 'CL=F'], ['oil_brent', 'BZ=F'], ['gas', 'NG=F']]],
  ['FX', [['usdidr', 'IDR=X'], ['usdcny', 'CNY=X'], ['usdjpy', 'JPY=X'], ['usdinr', 'INR=X'],
          ['eurusd', 'EURUSD=X'], ['dollar', 'DX-Y.NYB']]],
];

export default function DriverBuilder({ drivers, setDrivers, region = 'indonesia' }) {
  const update = (i, key, val) => setDrivers(drivers.map((d, j) => (j === i ? { ...d, [key]: val } : d)));
  const remove = (i) => setDrivers(drivers.filter((_, j) => j !== i));
  const add = (name = '', ticker = '', group = '') => setDrivers([...drivers, { name, ticker, group }]);
  const has = (name) => drivers.some((d) => d.name === name);

  return (
    <div className="field">
      <label>Drivers — the factor model this basket is regressed on (name · yfinance ticker · group)</label>
      <div className="tablewrap">
        <table className="sc">
          <thead><tr><th>name</th><th>ticker</th><th>group</th><th></th></tr></thead>
          <tbody>
            {drivers.length === 0 && (
              <tr><td colSpan={4} className="caption">No drivers yet — add at least one.</td></tr>
            )}
            {drivers.map((d, i) => (
              <tr key={i}>
                <td><input className="input" value={d.name} placeholder="market"
                  onChange={(e) => update(i, 'name', e.target.value)} /></td>
                <td><input className="input" value={d.ticker} placeholder="^JKSE"
                  onChange={(e) => update(i, 'ticker', e.target.value)} /></td>
                <td><input className="input" value={d.group} placeholder="Market"
                  onChange={(e) => update(i, 'group', e.target.value)} /></td>
                <td><button className="btn ghost" onClick={() => remove(i)} title="remove">✕</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8, alignItems: 'center' }}>
        <button className="btn ghost" onClick={() => add()}>+ Add driver</button>
        <span className="caption" style={{ margin: 0 }}>{region === 'indonesia' ? 'Indonesia' : 'US'} quick add:</span>
        {(QUICK[region] || QUICK.us).map(([n, t, g]) => (
          <button key={n} className="btn ghost" disabled={has(n)} onClick={() => add(n, t, g)}>{n} ({t})</button>
        ))}
      </div>
      {PALETTES.map(([grp, items]) => (
        <div key={grp} style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 6, alignItems: 'center' }}>
          <span className="caption" style={{ margin: 0, minWidth: 54 }}>{grp}:</span>
          {items.map(([n, t]) => (
            <button key={n} className="btn ghost" disabled={has(n)} onClick={() => add(n, t, grp)}>{n} ({t})</button>
          ))}
        </div>
      ))}
      <div className="caption" style={{ marginTop: 6 }}>
        Any yfinance ticker works — e.g. <span className="mono">^JKSE</span>, <span className="mono">IDR=X</span>,
        <span className="mono"> BZ=F</span>. FX enters as its own driver so the currency effect is stripped out.
        Coal/palm quick-adds are <b>equity proxies</b> (no free physical future), labelled as such — swap in a
        real price series if you have one.
      </div>
    </div>
  );
}
