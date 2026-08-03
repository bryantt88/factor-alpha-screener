# /concise-answer — Condense the Latest Answer

Take your **immediately preceding answer** and re-state it as tightly as possible. This is a compression pass on what you just said — do not add new analysis, do not re-run tools, do not fetch new information.

## What to produce
- A stripped-down version of the last answer that a busy reader can scan in seconds.
- **Point-form by default.** Use bullets. Only fall back to a sentence or two if the answer is genuinely a single fact.
- Lead with the bottom line. If the last answer ended in a recommendation or a question, put that first.

## Rules
- **Cut, don't rewrite.** Keep the same facts, numbers, file names, and conclusions — just remove hedging, preamble, transitions, and repetition.
- One idea per bullet. Max ~12 words per bullet where possible.
- Preserve anything load-bearing: specific numbers, dates, tickers, file paths, exact next actions.
- No new caveats, no new options, no filler ("as mentioned", "it's worth noting", "in summary").
- Keep `code`/paths in backticks so they stay clickable.
- Bold a short lead label on a bullet only when it aids scanning (e.g. **Status:**, **Blocker:**).
- If the last answer offered a choice, end with that choice as a one-line question.

## Length target
- Aim for **under ~120 words**. If the original was already short, return it near-verbatim rather than padding.

## Output
- Output only the condensed answer. No "Here is the concise version" preamble.
