# /compact — Session Compaction + Cumulative Memory

Two jobs, run in order every time:
**(A)** write a short handoff for the work done **since the last compact**, and
**(B)** fold that handoff into the **cumulative memory** so that opening this project fresh loads the full current state with zero re-reading.

Write as if briefing a colleague who knows the project well but has zero memory of the recent work.

**Guiding principle for the handoff: clear and straightforward beats complete.** A reader should understand what happened and what to do next in under 30 seconds. Use plain language and short declarative sentences. Lead each line with the thing that changed, then the outcome. Cut hedging, cut process ("investigated", "explored", "discussed"), cut anything the code already says. If a line doesn't change what the next session knows or does, delete it.

---

## Step 0 — Find the window

The compact covers **everything since the previous compact**, not just the last exchange (several working sessions may have passed without a `/compact`).

1. List `memory/session-compact-*.md`; the most recent date is the **window start**.
2. Everything from that point until now is in scope. If the conversation is a fresh reload, use `memory/daily-log.md` entries after the window start to reconstruct what happened.

---

## Step A — Write the handoff (short)

Save to `memory/session-compact-[YYYY-MM-DD].md`. **Max 300 words.** Compress hard — every line is either a fact or an action, never narration.

The first line after the title is a **one-sentence summary** of the whole window (the "if you read nothing else" line). Then the sections.

```
## COMPACT — [today] (covers since [window-start date])

**In one line:** [what this window accomplished, plainly]

### WHAT CHANGED
- [change → outcome, one line each. Code, decisions, and findings all go here.]

### WHERE THINGS STAND
- [file or component] — [what it does now, current truth]

### DO NEXT
1. [the single most important next action — specific enough to start cold]
2. [next, if any]
- Blocked on: [open fork or decision the user must make, one line — omit if none]

### DECISIONS LOCKED
- [decision] — [one-line why]
```

Rules for the lines:
- **One idea per line.** No semicolon-chained clauses.
- **Lead with the subject.** "Net debt now includes finance leases → ties to Yahoo" not "After investigating the discrepancy, we decided to...".
- **Name the file** when a line is about code.
- **State outcomes, not effort.** "ETN EBITDA recovered (was unverified)" not "spent time getting ETN to work".

Omit any empty section. Skip a results table unless a backtest/screen actually ran this window.

---

## Step B — Update the cumulative memory (the important part)

Memory lives in **two mirrored stores**; keep both current. Do NOT rewrite them wholesale — **merge incrementally**: update the lines that changed, add genuinely new durable facts, delete facts now false. Same fact must not live in two files.

**1. In-repo `memory/` (canonical, travels with the project):**
- `memory/project-roadmap.md` — update build-order status, "Status:" line, decisions locked, remaining items. This is the single source of truth for *where the project is*.
- `memory/daily-log.md` — append a dated entry for this window (this is the running narrative; it may be longer than the handoff).

**2. Auto-loaded store `~/.claude/projects/<slug>/memory/` (mirror, loaded at session start):**
- This is what makes "open the project and you already have everything" true — it is injected automatically next session.
- `MEMORY.md` is the **index only** — one `- [Title](file.md) — hook` line per memory file. Never put content in it.
- Each durable fact is one file (`build-state.md`, `hard-rules.md`, decisions, etc.). For every change this window: edit the relevant file so it reflects the *current* truth (not a changelog), add a new file + index line for a genuinely new durable fact, and delete any file (and its index line) that is now wrong.
- Convert relative dates to absolute. Cross-link related facts with `[[slug]]`.

**What counts as durable** (belongs in memory): project goal, locked decisions + their rationale, current build state, hard rules, where key logic lives and *why it's non-obvious*. **What does not** (leave in the handoff only): step-by-step narrative, transient debugging, anything the code/git already records.

---

## Definition of done
- `memory/session-compact-[today].md` written (≤300 words).
- `project-roadmap.md` + `daily-log.md` reflect current state.
- Auto-loaded `MEMORY.md` index and its files updated so a cold reopen needs no catch-up reading.
- State one line to the user: what the next session should do first.
