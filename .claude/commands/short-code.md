# /short-code — Compress Code Without Changing Behavior

Shorten and tighten the target code so it is more concise and efficient, while preserving **100%
identical behavior**. This is a pure length/efficiency pass — NOT a bug fix, NOT a feature change, NOT
a redesign. Every function must do exactly what it did before: same inputs, same outputs, same side
effects. (For the AI-Power Stack Screener this especially means: identical α/β/idiosyncratic numbers,
identical Track tags, identical scorecard values.)

## Scope
- Operate on the file(s) named in the argument (e.g. `/short-code src/regression/engine.py`).
- If no argument is given, ask which file(s) to target — never guess and edit the whole repo.
- Work one file at a time. Read the ENTIRE file before editing.

## The one rule that overrides everything
**Do not change what any function does.** If a shortening could alter a single output, printed string,
JSON key, written file, numeric result, edge case, exception, or control-flow outcome — do NOT make
it. When in doubt, leave it. A slightly longer but correct line always beats a shorter risky one.

## What you MAY shorten (only when behavior is provably identical)
- Remove **dead code**: unreachable branches, unused variables, unused imports, and functions that are
  provably never called (grep to confirm zero references first).
- Collapse verbose constructs into idiomatic equivalents with identical semantics: comprehensions,
  `any()`/`all()`, `dict.get(k, default)`, ternaries, tuple unpacking, `enumerate`, chained
  comparisons, `str.join`.
- Eliminate redundant intermediate variables and duplicated expressions.
- Merge genuinely duplicated logic into a helper — only if the merged version is byte-for-byte
  equivalent in behavior.
- Combine trivially splittable statements; drop no-op lines.

## What you MUST NOT touch
- Public function/class names, signatures, argument order/defaults, or return types.
- Any user-visible output: `print(...)` text, report formatting, JSON keys/structure, filenames.
- Config constants, thresholds, or numeric literals (e.g. windows like 252/90/63, the $2B floor).
- Exception handling scope (don't widen/narrow `try` blocks or swallow errors differently).
- Comments that explain **why** (rationale, gotchas, non-obvious decisions — e.g. the α+ε convention,
  the futures-not-ETFs note) — this codebase is intentionally documented; keep those. You may delete a
  comment ONLY if it literally restates the code on the next line.
- Anything you are not certain is safe.

## Process
1. Read the whole target file.
2. List the specific shortenings you intend (each with why it's behavior-preserving). If a change is
   borderline, drop it from the list.
3. Apply the edits.
4. **Verify** (mandatory, in order):
   - `python -m py_compile <file>` — must pass.
   - Run a relevant smoke check: `pytest tests/ -q` if the file has test coverage, otherwise at minimum
     import it (`python -c "import src.<module>"`) to confirm nothing broke.
5. Report: lines before → after (net delta), and a short bullet list of what was compressed. State
   plainly that no behavior changed and what you ran to confirm it.

## Output
- Keep the summary concise (this project prefers point-form).
- If you found nothing safe to shorten, say so — do not force risky edits to show progress.
