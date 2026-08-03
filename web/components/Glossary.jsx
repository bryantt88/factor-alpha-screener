'use client';

const G = [
  ['Idiosyncratic return (α + ε)',
    'The stock\'s OWN move, after the factors (market, rates, oil, gas) are stripped out. It is the ' +
    'sum of the persistent drift α and the daily surprises ε. This is the headline "is it rising on ' +
    'its own merit?" number. Never plotted as bare ε (that always sums to zero and erases the trend).'],
  ['Alpha (α)',
    'The intercept of the regression — the average DAILY return the factors do NOT explain, i.e. the ' +
    'steady, persistent drift. "α (annualized)" is that daily drift × 252.'],
  ['Epsilon (ε)',
    'The day-by-day leftover the model missed (the noise around the drift). By construction it ' +
    'averages to zero over the window.'],
  ['α t-stat',
    'How many standard errors α sits above zero. Rule of thumb: |t| ≳ 2 means the alpha is ' +
    'statistically real, not luck. BE example: t = 1.86 → borderline, NOT quite significant.'],
  ['p-value',
    'The chance you\'d see an alpha this big if the true alpha were zero. p < 0.05 = "statistically ' +
    'significant." (t-stat and p-value are two views of the same test.)'],
  ['Information ratio (IR)',
    'Annualized α ÷ the volatility of ε (idiosyncratic risk). The QUALITY of the alpha — steady ' +
    'outperformance scores high; a big-but-jumpy residual scores low. The scorecard ranks by this, ' +
    'not by raw return. (Numerically IR ≈ the t-stat here.)'],
  ['R²',
    'The share of the stock\'s daily moves the factors explain (0–1). Low R² (these names are ~0.2–0.3) ' +
    'means most of the move is idiosyncratic — which is why idio ≈ raw for them.'],
    ['Why we don\'t plot "compounded alpha"',
    'α is a tiny DAILY drift. Compounding it every day for a year — (1+α)^252 — explodes exponentially ' +
    '(a ~1%/day α ⇒ ~+1500%/yr), which flatters the number, so we never headline it. And the real ' +
    'idiosyncratic path (α+ε) always lands BELOW that smooth line, because compounding noise loses ' +
    'ground (−10% then +10% = −1%; "volatility drag"). That made the old drift overlay misleading, so ' +
    'the Alpha tab now just shows the idiosyncratic curve — judge whether the alpha is REAL from the ' +
    'α t-stat / info ratio, not by eye.'],
  ['Beta (β) — one definition everywhere',
    'Every beta in the app is the model\'s PARTIAL (multivariate) beta: a factor\'s effect on the ' +
    'stock after holding the other factors constant. It appears in the scorecard, the Regression-fit ' +
    'table, and the Decoupling chart — the same number, no competing "simple" beta. (A univariate ' +
    'beta — the stock vs one factor alone, TradingView-style — can differ, but we don\'t show it to ' +
    'avoid two conflicting numbers.)'],
  ['Rolling beta vs static beta (Decoupling tab)',
    'Rolling = that SAME partial beta computed over a moving 90-day window (the trajectory). The ' +
    'dashed line = the model\'s full-year partial beta — i.e. exactly the table value. So rolling and ' +
    'table now reconcile: the solid line wiggles around the dashed table value. A steadily falling ' +
    'line = the stock decoupling from that commodity over the year. (Correlation, the other panel, is ' +
    'a separate unitless −1..1 measure, not a beta.)'],
  ['Combined oil β (boss mode)',
    'In boss mode both WTI and Brent are factors, but they\'re ~0.95 correlated so their individual ' +
    'betas are unstable. Their SUM is stable — read that instead of either one.'],
  ['Additive vs compounded return (IMPORTANT)',
    'Compounded = (1+r) multiplied through − 1: the real money return (what the headline metrics and ' +
    'all line charts use). Additive = Σ of daily returns: used ONLY in the Attribution tab, because ' +
    'the factor slices must sum linearly to a total. For a big mover the two diverge a lot (BE: raw ' +
    '+760% compounded vs +278% additive) — that\'s expected, not an error.'],
  ['Verdict: Rising on its own / Turning up underneath / Just riding the wave / No clear own trend',
    'Rising on its own = price up AND idiosyncratic return up (a real winner). Turning up underneath ' +
    '= price down but idiosyncratic return up (improving beneath a weak price). Just riding the wave ' +
    '= price up but idiosyncratic return flat/down (it only rose with its sector/commodity, not on ' +
    'its own). No clear idiosyncratic trend = nothing decisive.'],
  ['Confidence tag: Real / Not proven / Likely luck',
    'How sure we are the idiosyncratic return is genuine, not luck. Real = statistically solid (t ≥ 2, ' +
    'i.e. under ~5% chance of being noise). Not proven = leaning real but not there yet (t between 1 ' +
    'and 2). Likely luck = weak or negative (t < 1). It grades the idiosyncratic return\'s reliability.'],
  ['Tracking-noise ⚠ (on α+ε)',
    'Fires when a large idiosyncratic return sits on a HIGH R². Then much of the move is already ' +
    'factor-tracked, so the big α+ε may be roll / non-synchronous-close noise, not a genuine own-story.'],
  ['Factor modes',
    '4factor = market + rates + WTI + Henry Hub. commodity = WTI + Henry Hub only. boss = market + ' +
    'WTI + Brent + Henry Hub (your boss\'s literal spec).'],
  ['The four gates',
    'Gate 1 Size (market cap ≥ floor) · Gate 2 Fundamentals (margin, leverage, EPS beat, valuation) · ' +
    'Gate 3 AI exposure (Gemini reads real news, you approve) · Gate 4 Idiosyncratic (the regression).'],
];

export default function Glossary() {
  return (
    <div className="card" style={{ marginTop: 8 }}>
      {G.map(([term, def]) => (
        <div key={term} style={{ padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
          <div style={{ fontWeight: 800, marginBottom: 4 }}>{term}</div>
          <div style={{ color: 'var(--muted)', fontSize: '.9rem' }}>{def}</div>
        </div>
      ))}
    </div>
  );
}
