#!/usr/bin/env python3
"""Render sanitized JSON metrics with the Claude statusline's exact ANSI palette."""
import argparse
import json
import math
import re
import sys
import time

RESET = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"
GREEN = "\033[32m"
BLUE = "\033[34m"
CYAN = "\033[36m"


def clean(value):
    # Paths/branches/model names must never inject terminal control sequences.
    return re.sub(r"[\x00-\x1f\x7f-\x9f]", "", str(value))[:240]


def number(value):
    return (
        value
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        else None
    )


def pct(value):
    value = number(value)
    return None if value is None else max(0, min(100, int(value + 0.5)))


def shade(value):
    return (
        DIM
        if value is None
        else "\033[31m" if value >= 85 else "\033[33m" if value >= 60 else GREEN
    )


def metric(label, value):
    value = pct(value)
    filled = 0 if value is None else (value * 8 + 50) // 100
    color = shade(value)
    bar = color + "█" * filled + RESET + DIM + "█" * (8 - filled) + RESET
    return f'{label} {bar} {color}{BOLD}{value if value is not None else "?"}%{RESET}'


def countdown(reset, now):
    reset = number(reset)
    if reset is None or reset <= now:
        return ""
    diff = int(reset - now)
    days, hours, minutes = diff // 86400, diff % 86400 // 3600, diff % 3600 // 60
    text = (
        f"{days}d{hours}h"
        if days
        else f"{hours}h{minutes:02d}m" if hours else f"{minutes}m" if minutes else "<1m"
    )
    return f" {DIM}(in {text}){RESET}"


def render(data, now=None, color=True):
    now = time.time() if now is None else now
    directory = f'{BOLD}{clean(data.get("cwd", "?"))}{RESET}'
    branch = data.get("branch")
    if branch:
        directory += f" {DIM}git:({RESET}{BLUE}{clean(branch)}{RESET}{DIM}){RESET}"
        if data.get("dirty"):
            directory += f" \033[33m{BOLD}*{RESET}"
    parts = [directory]
    if data.get("context_percent") is not None:
        parts.append(metric("ctx", data.get("context_percent")))
    for label, key in [("5h", "five_hour"), ("7d", "seven_day")]:
        window = data.get(key) or {}
        reset = number(window.get("resets_at"))
        observed = number(window.get("observed_at"))
        stale = observed is None or not 0 <= now - observed <= 120
        expired = reset is not None and reset <= now
        value = None if stale or expired else window.get("used_percent")
        parts.append(
            metric(label, value)
            + (countdown(reset, now) if not stale and not expired else "")
        )
    cost = number(data.get("cost_usd"))
    if cost is not None and cost >= 0:
        parts.append(f"{GREEN}${cost:.2f}{RESET}")
    if data.get("model"):
        parts.append(f'{BOLD}{clean(data["model"])}{RESET}')
    if data.get("effort"):
        parts.append(f'{CYAN}{clean(data["effort"])}{RESET}')
    line = f" {DIM}·{RESET} ".join(parts)
    return line if color else re.sub(r"\x1b\[[0-9;]*m", "", line)


def demo(now):
    return dict(
        cwd="~/myproject",
        branch="main",
        dirty=True,
        context_percent=36,
        five_hour=dict(used_percent=66, resets_at=now + 240, observed_at=now),
        seven_day=dict(
            used_percent=36, resets_at=now + 5 * 86400 + 21 * 3600, observed_at=now
        ),
        cost_usd=62.95,
        model="Codex",
        effort="xhigh",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--no-color", action="store_true")
    args = parser.parse_args()
    now = time.time()
    data = demo(now) if args.demo else json.load(sys.stdin)
    if not isinstance(data, dict):
        parser.error("Expected a JSON object")
    print(render(data, now, color=not args.no_color))


if __name__ == "__main__":
    main()
