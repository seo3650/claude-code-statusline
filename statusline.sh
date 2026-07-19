#!/bin/bash
input=$(cat)

# --- Colors ---
RESET='\033[0m'
BOLD='\033[1m'
DIM='\033[2m'
GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
CYAN='\033[36m'
MAGENTA='\033[35m'
BLUE='\033[34m'

# Green < 60%, yellow 60-84%, red >= 85%. Non-numeric ("?", empty) stays dim.
color_for_pct() {
  local v="$1"
  case "$v" in
    ''|'?'|*[!0-9]*) echo "$DIM"; return ;;
  esac
  if [ "$v" -ge 85 ]; then echo "$RED"
  elif [ "$v" -ge 60 ]; then echo "$YELLOW"
  else echo "$GREEN"
  fi
}

# 8-cell block bar, one glyph (█ full block) at uniform ink density for both
# filled and empty cells — color alone (threshold color vs DIM) tells them
# apart. Earlier attempts mixed glyphs of different density (▓▒░, ▌) which
# read as extra "colors" even under one ANSI color, and mixing █ with ▌
# produced a rendering gap in the cmux renderer. 8 discrete levels
# (12.5%p per step); no partial-cell glyph, so no repeat of either bug.
BAR_WIDTH=8
make_bar() {
  local pct="$1" color filled empty fill_str empty_str
  case "$pct" in
    ''|'?'|*[!0-9]*)
      printf -v empty_str "%${BAR_WIDTH}s" ""
      echo -e "${DIM}${empty_str// /█}${RESET}"
      return
      ;;
  esac
  color=$(color_for_pct "$pct")
  # Round to nearest cell (+50 before integer-dividing by 100) so e.g. 60%
  # fills 5/8 cells (~62.5%) rather than flooring to 4/8 (50%), which read
  # as visibly less than the number next to it.
  filled=$(((pct * BAR_WIDTH + 50) / 100))
  [ "$filled" -gt "$BAR_WIDTH" ] && filled=$BAR_WIDTH
  empty=$((BAR_WIDTH - filled))
  fill_str="" empty_str=""
  [ "$filled" -gt 0 ] && printf -v fill_str "%${filled}s" "" && fill_str="${fill_str// /█}"
  [ "$empty" -gt 0 ] && printf -v empty_str "%${empty}s" "" && empty_str="${empty_str// /█}"
  echo -e "${color}${fill_str}${RESET}${DIM}${empty_str}${RESET}"
}

# --- 기본 정보 ---
model=$(echo "$input" | jq -r '.model.display_name')
model_id=$(echo "$input" | jq -r '.model.id // ""')
if [[ "$model" != *"1M"* && "$model" != *"1m"* ]]; then
  case "$model_id" in
    *-1m|*'[1m]') model="${model} (1M)" ;;
  esac
fi

# Fable stands out (separate usage-credits pool, not covered by rate_limits below)
case "$model_id" in
  *fable*) model_color="$MAGENTA" ;;
  *) model_color="$BOLD" ;;
esac

cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // ""')
dir_display="${cwd/#$HOME/~}"

remaining=$(echo "$input" | jq -r '.context_window.remaining_percentage // 0')
cost=$(echo "$input" | jq -r '.cost.total_cost_usd // 0')
cost_fmt=$(printf '%.2f' "$cost" 2>/dev/null || echo "$cost")
remaining_int=${remaining%.*}
used_int=$((100 - remaining_int))

# --- Effort level (reasoning effort: low/medium/high/xhigh) ---
effort=$(echo "$input" | jq -r '.effort.level // ""')
[ -n "$effort" ] && effort_disp=" ${DIM}·${RESET} ${CYAN}${effort}${RESET}" || effort_disp=""

# --- Git (branch + dirty) ---
git_info=""
if [ -n "$cwd" ]; then
  branch=$(git -C "$cwd" symbolic-ref --short HEAD 2>/dev/null \
           || git -C "$cwd" rev-parse --short HEAD 2>/dev/null)
  if [ -n "$branch" ]; then
    dirty=""
    if [ -n "$(git -C "$cwd" status --porcelain 2>/dev/null)" ]; then
      dirty=" ${YELLOW}${BOLD}*${RESET}"
    fi
    git_info=" ${DIM}git:(${RESET}${BLUE}${branch}${RESET}${DIM})${RESET}${dirty}"
  fi
fi

# --- Usage Limit (stdin .rate_limits — Pro/Max only, after first API response) ---
# rate_limits is account-wide, but each session only ever sees it refresh on
# its OWN API responses — a quiet session just keeps re-displaying whatever it
# last saw, drifting behind other active sessions on the same account. Fix:
# every session writes its own reading into a shared cache file (only when the
# value actually changed, so a re-render doesn't stamp a fake "just updated"
# time on unchanged data), and always displays whichever reading — its own or
# another session's — is newest. Pure local file, no API calls either way.
CACHE_FILE="$HOME/.claude/.statusline_ratelimits.json"
[ -f "$CACHE_FILE" ] || echo '{}' >"$CACHE_FILE" 2>/dev/null

sync_window() {
  local key="$1" pct="$2" resets="$3" cached_pct cached_resets tmp should_write=0
  [ -z "$pct" ] && return
  cached_pct=$(jq -r --arg k "$key" '.[$k].used_percentage // empty' "$CACHE_FILE" 2>/dev/null)
  cached_resets=$(jq -r --arg k "$key" '.[$k].resets_at // empty' "$CACHE_FILE" 2>/dev/null)
  if [ -z "$cached_pct" ]; then
    # No cache entry yet — anything is an improvement.
    should_write=1
  elif [ -n "$resets" ] && [ -n "$cached_resets" ] && [ "$resets" != "$cached_resets" ]; then
    # resets_at moved — the window actually rolled over, so a lower % here
    # is the legitimate post-reset value, not a stale session regressing us.
    should_write=1
  elif awk -v a="$pct" -v b="$cached_pct" 'BEGIN{exit !(a > b)}' 2>/dev/null; then
    # Same window: usage only climbs until reset, so only accept readings
    # that move forward. Without this, a session that hasn't talked in a
    # while can wake up on its refreshInterval tick and overwrite a fresher,
    # higher reading from another session with its own older, lower one.
    should_write=1
  fi
  if [ "$should_write" = "1" ] && [ "$pct" != "$cached_pct" ]; then
    tmp="${CACHE_FILE}.tmp.$$"
    jq --arg k "$key" --argjson pct "$pct" --argjson resets "${resets:-null}" --argjson now "$(date +%s)" \
      '.[$k] = {used_percentage: $pct, resets_at: $resets, updated_at: $now}' \
      "$CACHE_FILE" >"$tmp" 2>/dev/null && mv "$tmp" "$CACHE_FILE"
  fi
}
sync_window "five_hour" "$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')" \
  "$(echo "$input" | jq -r '.rate_limits.five_hour.resets_at // empty')"
sync_window "seven_day" "$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')" \
  "$(echo "$input" | jq -r '.rate_limits.seven_day.resets_at // empty')"

fmt_pct() {
  local v="$1"
  [ -z "$v" ] && { echo "?"; return; }
  printf '%.0f' "$v" 2>/dev/null || echo "$v"
}
h5_cache_pct=$(jq -r '.five_hour.used_percentage // empty' "$CACHE_FILE" 2>/dev/null)
h5_cache_resets=$(jq -r '.five_hour.resets_at // empty' "$CACHE_FILE" 2>/dev/null)
d7_cache_pct=$(jq -r '.seven_day.used_percentage // empty' "$CACHE_FILE" 2>/dev/null)
d7_cache_resets=$(jq -r '.seven_day.resets_at // empty' "$CACHE_FILE" 2>/dev/null)
usage_session=$(fmt_pct "$h5_cache_pct")
usage_week=$(fmt_pct "$d7_cache_pct")

# Time left until each rate-limit window resets (from .resets_at, a unix epoch)
fmt_remaining() {
  local resets_at="$1" now diff d h m
  [ -z "$resets_at" ] && return
  now=$(date +%s)
  diff=$((resets_at - now))
  [ "$diff" -lt 0 ] && diff=0
  d=$((diff / 86400))
  h=$(((diff % 86400) / 3600))
  m=$(((diff % 3600) / 60))
  if [ "$d" -gt 0 ]; then
    printf '%dd%dh' "$d" "$h"
  elif [ "$h" -gt 0 ]; then
    printf '%dh%02dm' "$h" "$m"
  elif [ "$m" -gt 0 ]; then
    printf '%dm' "$m"
  else
    # Under a minute left (or already past reset) — "0m" reads as "already
    # done", so show "<1m" to mean the window is about to roll over.
    printf '<1m'
  fi
}
h5_remaining=$(fmt_remaining "$h5_cache_resets")
d7_remaining=$(fmt_remaining "$d7_cache_resets")
# "(in Xm)" — countdown to when the rate-limit window resets.
[ -n "$h5_remaining" ] && h5_reset_disp="${DIM}(in ${h5_remaining})${RESET}" || h5_reset_disp=""
[ -n "$d7_remaining" ] && d7_reset_disp="${DIM}(in ${d7_remaining})${RESET}" || d7_reset_disp=""

ctx_color=$(color_for_pct "$used_int")
h5_color=$(color_for_pct "$usage_session")
d7_color=$(color_for_pct "$usage_week")

ctx_bar=$(make_bar "$used_int")
h5_bar=$(make_bar "$usage_session")
d7_bar=$(make_bar "$usage_week")

# --- 출력 ---
echo -e "${BOLD}${dir_display}${RESET}${git_info} ${DIM}·${RESET} ctx ${ctx_bar} ${ctx_color}${BOLD}${used_int}%${RESET} ${DIM}·${RESET} 5h ${h5_bar} ${h5_color}${BOLD}${usage_session}%${RESET}${h5_reset_disp:+ ${h5_reset_disp}} ${DIM}·${RESET} 7d ${d7_bar} ${d7_color}${BOLD}${usage_week}%${RESET}${d7_reset_disp:+ ${d7_reset_disp}} ${DIM}·${RESET} ${GREEN}\$${cost_fmt}${RESET} ${DIM}·${RESET} ${model_color}${model}${RESET}${effort_disp}"
