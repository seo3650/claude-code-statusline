#!/usr/bin/env python3
"""Read local metrics without saving conversation content or reading credentials."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time
from rpc import CodexRPC
from statusline import render


def context_percent(path):
    if not path:
        return None
    path = Path(path).resolve()
    home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).resolve()
    if not path.is_relative_to(home / "sessions") or path.suffix != ".jsonl":
        return None
    info = None
    with path.open("rb") as file:
        size = file.seek(0, 2)
        start = max(0, size - 2 * 1024 * 1024)
        file.seek(start)
        if start:
            file.readline()
        for line in file:
            try:
                event = json.loads(line)
            except (ValueError, UnicodeDecodeError):
                continue
            if not isinstance(event, dict):
                continue
            payload = event.get("payload", {})
            if not isinstance(payload, dict):
                continue
            if (
                event.get("type") == "event_msg"
                and payload.get("type") == "token_count"
            ):
                info = payload.get("info")
    if not isinstance(info, dict):
        return None
    window = info.get("model_context_window")
    last = info.get("last_token_usage") or {}
    used = last.get("total_tokens")
    if (
        isinstance(window, (int, float))
        and window > 0
        and isinstance(used, (int, float))
    ):
        return used / window * 100
    return None


def git(cwd, *args):
    result = subprocess.run(
        ["git", "-C", cwd, *args], capture_output=True, text=True, timeout=3
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def snapshot(thread_id, cwd):
    now = time.time()
    result = {"cwd": cwd}
    with CodexRPC(cwd=cwd) as rpc:
        rate = rpc.call("account/rateLimits/read", timeout=15)
        pools = rate.get("rateLimitsByLimitId") or {}
        pool = pools.get("codex") or rate.get("rateLimits") or {}
        for window in [pool.get("primary") or {}, pool.get("secondary") or {}]:
            key = {300: "five_hour", 10080: "seven_day"}.get(
                window.get("windowDurationMins")
            )
            if key:
                result[key] = {
                    "used_percent": window.get("usedPercent"),
                    "resets_at": window.get("resetsAt"),
                    "observed_at": now,
                }
        if thread_id:
            thread = rpc.call(
                "thread/read",
                {"threadId": thread_id, "includeTurns": False},
                timeout=15,
            )["thread"]
            cwd = thread.get("cwd") or cwd
            result.update(
                cwd=cwd, model=thread.get("model"), effort=thread.get("reasoningEffort")
            )
            result["context_percent"] = context_percent(thread.get("path"))
    result["branch"] = git(cwd, "symbolic-ref", "--short", "HEAD") or git(
        cwd, "rev-parse", "--short", "HEAD"
    )
    result["dirty"] = bool(git(cwd, "status", "--porcelain"))
    home = str(Path.home())
    if cwd == home or cwd.startswith(home + "/"):
        result["cwd"] = "~" + cwd[len(home) :]
    # Reliable thread-dollar amounts are not exposed here; keep unknown.
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--thread")
    parser.add_argument("--cwd", default=os.getcwd())
    parser.add_argument("--watch", action="store_true")
    args = parser.parse_args()
    if args.thread and not re.fullmatch(r"[0-9a-fA-F-]{36}", args.thread):
        parser.error("Expected a thread UUID")
    while True:
        try:
            data = snapshot(args.thread, args.cwd)
            failure = False
        except Exception:
            data = {"cwd": args.cwd}
            failure = True
        text = render(data, color=os.isatty(1))
        if failure:
            text += " · 조회 실패"
        if args.watch:
            print("\033[?7l\r\033[2K" + text, end="", flush=True)
        else:
            print(text)
        if not args.watch:
            return
        time.sleep(60)


if __name__ == "__main__":
    main()
