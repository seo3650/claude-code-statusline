# claude-code-statusline

A single-file [Claude Code](https://code.claude.com/docs/en/statusline) status line that shows context usage, **account-wide rate limits (5h / 7d) with reset countdowns**, session cost, git state, model, and reasoning effort — as compact colored bars.

```
~/myproject git:(main) * · ctx ████████ 36% · 5h ████████ 66% (in 4m) · 7d ████████ 36% (in 5d21h) · $62.95 · Opus · xhigh
```

Each segment: a directory + git branch, then an 8-cell bar per metric where the filled portion is colored by threshold (green < 60%, yellow 60–84%, red ≥ 85%) and the empty track is dim.

## Why this one

Most rate-limit status lines just print whatever value the *current* session last saw. But `rate_limits` is **account-wide**, while each Claude Code session only refreshes it on its *own* API responses. So if you run several sessions at once, a quiet session keeps showing a stale number and drifts behind the ones doing actual work.

This script fixes that with a tiny **shared cache file** (`~/.claude/.statusline_ratelimits.json`):

- Every session writes its reading into the cache — but only when the value actually changed.
- Within the same rate-limit window (`resets_at` unchanged), usage only ever climbs until reset, so the cache only accepts a **higher** reading. This stops a session that just woke up on its timer from overwriting a fresher, higher number with its own older, lower one.
- When `resets_at` moves (the window genuinely rolled over), a lower post-reset value is accepted.
- Every session always *displays* the newest cached reading — its own or another session's.

No API calls, no keychain reads — just one local JSON file that all sessions share.

## Features

- **ctx** — context window used %, 8-cell bar. Shows `?` with a dim empty bar until the session's first API response, since Claude Code has no context reading to report before then
- **5h / 7d** — account rate-limit windows (Claude Pro/Max only), each with a `(in Xm)` reset countdown
- **cost** — session cost in USD
- **model** — display name; **Fable is highlighted in magenta** because it draws on a separate usage-credits pool that `rate_limits` doesn't cover
- **git** — branch + a `*` dirty flag
- **effort** — current reasoning effort (`low`/`medium`/`high`/`xhigh`), when the model exposes it

## Requirements

- Claude Code **2.1.97+** (for `refreshInterval`)
- [`jq`](https://jqlang.org/) on your `PATH`
- `bash`
- A terminal with ANSI color and the `█` glyph (any modern one)
- 5h / 7d bars appear only for **Claude Pro/Max** subscribers, and only after the first API response of a session

## Install

```bash
# 1. Drop the script in place
curl -fsSL https://raw.githubusercontent.com/seo3650/claude-code-statusline/main/statusline.sh \
  -o ~/.claude/statusline.sh
chmod +x ~/.claude/statusline.sh
```

Then add this to `~/.claude/settings.json` (merge it into your existing settings — don't overwrite the whole file):

```json
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/statusline.sh",
    "refreshInterval": 60
  }
}
```

See [`settings.snippet.json`](./settings.snippet.json) for the same block.

> **Gotcha — `refreshInterval` is in _seconds_, not milliseconds.** The docs say "every N seconds"; `60` means one minute. A value like `60000` is ~16.7 hours, so it looks like the timer never fires.

`refreshInterval` re-runs the script on a timer so 5h/7d/cost stay current even while a session sits idle (the event-driven triggers — new message, `/compact`, permission-mode change, vim-mode toggle — go quiet when nothing is happening).

> **`refreshInterval` is read once at session start.** Adding or changing it doesn't affect sessions that are already running — restart them (`/exit` then `claude --continue` keeps the conversation) for the timer to register. Editing `statusline.sh` itself *is* picked up on the next event, no restart needed.

## Customize

- **Bar width** — change `BAR_WIDTH=8` near the top. Higher = finer resolution (10 → 10%/step), but a longer line.
- **Color thresholds** — edit `color_for_pct()` (defaults: green < 60, yellow < 85, red otherwise).
- **Glyph** — the bar uses a single `█` for both filled and empty cells, distinguished by color only. This deliberately avoids mixing block glyphs of different density (`▓ ▒ ░ ▌`), which can read as extra "colors" or render as a gap in some terminals.

## License

MIT — see [LICENSE](./LICENSE).

## Codex에서도 사용

같은 디자인을 Codex에서 사용하는 방법은 [Codex 설정과 표시기](codex/README.md)를
참조하세요. 내장 statusline의 제약과 실제 값/알 수 없는 값을 구분해 설명합니다.
