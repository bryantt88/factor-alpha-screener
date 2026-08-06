'use client';
// Trade-ideas panel — reads data.opportunity (built server-side) and shows ONLY the threshold-gated
// trades: directional longs, market-neutral pairs, and the factor-hedged book (or an honest "no trade").
// The per-stock read/category for EVERY name lives in the ranked table below (one place, no duplication).
import { pct, num } from '@/lib/format';

const SIG_PILL = { improving: 'pass', weakening: 'fail', flat: 'neutral' };
const SIG_ARROW = { improving: '▲', weakening: '▼', flat: '·' };
function Signal({ sig }) {
  if (!sig) return null;
  return (
    <span className={`pill ${SIG_PILL[sig.state] || 'neutral'}`}
      title={`own-story return over the last ${sig.window} trading days (~${Math.round(sig.window / 21)} months)`}>
      recent {SIG_ARROW[sig.state] || ''} {pct(sig.recentIdio)} {sig.state}
    </span>
  );
}

function leg(l) {
  const side = l.weight >= 0 ? 'long' : 'short';
  return `${side} ${Math.abs(l.weight).toFixed(2)}× ${l.ticker}`;
}

export default function Opportunity({ data }) {
  const opp = data && data.opportunity;
  if (!opp) return null;
  const byTicker = Object.fromEntries(opp.reads.map((r) => [r.ticker, r]));
  const hasTrades = !opp.none;

  return (
    <section className="section">
      <div className="sechead">
        <span className="secnum">◎</span><h3>Trade ideas</h3>
        <span className="tag">what to actually do</span>
      </div>
      <div className="secsub">
        The actionable shortlist — long the names whose gains are <b>genuinely their own</b>, hedge the factor risk so what's
        left is pure stock-picking. Nothing appears unless it clears the bar. (Every name's read is in the ranked table below.)
      </div>

      {opp.none ? (
        <div className="callout" style={{ marginTop: 10 }}>
          <b>No trade idea meets the bar.</b> {opp.message}
        </div>
      ) : (
        <div className="verdict" style={{ marginTop: 6 }}><b>{opp.message}</b></div>
      )}

      {/* Directional longs */}
      {opp.longs.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <div className="eyebrow">Directional longs</div>
          {opp.longs.map((t) => {
            const r = byTicker[t];
            return (
              <div className="card" key={t} style={{ marginTop: 8 }}>
                <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                  <span className="pill pass">LONG {t}</span>
                  <span className="mono">own-story {pct(r.idio)}</span>
                  <span className="mono">quality (IR) {num(r.ir)}</span>
                  <span className="mono">t {num(r.tstat)}</span>
                  <Signal sig={r.signal} />
                </div>
                <div className="caption" style={{ marginTop: 6 }}>{r.note}</div>
              </div>
            );
          })}
        </div>
      )}

      {/* Neutral pairs */}
      {opp.pairs.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <div className="eyebrow">Market-neutral pairs</div>
          {opp.pairs.map((p, i) => (
            <div className="card" key={i} style={{ marginTop: 8 }}>
              <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                <span className="pill pass">LONG {p.long}</span>
                <span className="pill fail">SHORT {num(p.hedgeRatio)}× {p.short}</span>
                <span className="mono">neutralises {p.factor}</span>
                <span className="caption" style={{ margin: 0 }}>overlap {num(p.cos)}</span>
              </div>
              <div className="caption" style={{ marginTop: 6 }}>{p.note}</div>
            </div>
          ))}
        </div>
      )}

      {/* Factor-hedged book */}
      {hasTrades && opp.book && opp.book.hedges.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <div className="eyebrow">Factor-hedged book <span className="caption" style={{ margin: 0 }}>— works for any basket</span></div>
          <div className="card" style={{ marginTop: 8 }}>
            <div><b>Long:</b> {opp.book.longs.map(leg).join(', ')}</div>
            <div style={{ marginTop: 4 }}><b>Hedge:</b> {opp.book.hedges.map(leg).join(', ')}</div>
            <div className="caption" style={{ marginTop: 6 }}>{opp.book.note}</div>
          </div>
        </div>
      )}
    </section>
  );
}
