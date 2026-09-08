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
from statusline import BOLD, BLUE, CYAN, DIM, GREEN, RESET, render

THREAD_ID = re.compile(r"([0-9a-fA-F-]{36})\.jsonl$")
TMUX_STYLES = {
    RESET: "#[default]",
    DIM: "#[dim]",
    BOLD: "#[bold]",
    GREEN: "#[fg=green]",
    BLUE: "#[fg=blue]",
    CYAN: "#[fg=cyan]",
    "\033[31m": "#[fg=red]",
    "\033[33m": "#[fg=yellow]",
}


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


def _recent_thread_ids(started_at):
    home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).resolve()
    candidates = []
    for path in (home / "sessions").glob("**/*.jsonl"):
        try:
            modified = path.stat().st_mtime
        except OSError:
            continue
        match = THREAD_ID.search(path.name)
        if match and modified >= started_at - 2:
            candidates.append((modified, match.group(1)))
    return [thread_id for _modified, thread_id in sorted(candidates, reverse=True)]


def snapshot(thread_id, cwd, started_at=None):
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
        thread = None
        if thread_id:
            thread = rpc.call(
                "thread/read",
                {"threadId": thread_id, "includeTurns": False},
                timeout=15,
            )["thread"]
        elif started_at:
            wanted_cwd = Path(cwd).resolve()
            for candidate_id in _recent_thread_ids(started_at):
                candidate = rpc.call(
                    "thread/read",
                    {"threadId": candidate_id, "includeTurns": False},
                    timeout=15,
                )["thread"]
                candidate_cwd = candidate.get("cwd")
                if candidate_cwd and Path(candidate_cwd).resolve() == wanted_cwd:
                    thread_id = candidate_id
                    thread = candidate
                    break
        if thread:
            cwd = thread.get("cwd") or cwd
            result.update(
                cwd=cwd, model=thread.get("model"), effort=thread.get("reasoningEffort")
            )
            result["context_percent"] = context_percent(thread.get("path"))
            result["_thread_id"] = thread_id
    result["branch"] = git(cwd, "symbolic-ref", "--short", "HEAD") or git(
        cwd, "rev-parse", "--short", "HEAD"
    )
    result["dirty"] = bool(git(cwd, "status", "--porcelain"))
    home = str(Path.home())
    if cwd == home or cwd.startswith(home + "/"):
        result["cwd"] = "~" + cwd[len(home) :]
    # Reliable thread-dollar amounts are not exposed here; keep unknown.
    return result


def refresh_seconds(thread_id, data):
    return 60 if thread_id and data.get("context_percent") is not None else 2


def render_tmux(data, now=None):
    safe = dict(data)
    for key in ("cwd", "branch", "model", "effort"):
        if safe.get(key) is not None:
            # In a tmux format, ## is a literal #. This prevents untrusted git
            # metadata or paths from injecting status-format directives.
            safe[key] = str(safe[key]).replace("#", "##")
    line = render(safe, now, color=True)
    for ansi, tmux in TMUX_STYLES.items():
        line = line.replace(ansi, tmux)
    return line


def tmux_session_exists(socket, session):
    return (
        subprocess.run(
            ["tmux", "-L", socket, "has-session", "-t", session],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
        ).returncode
        == 0
    )


def publish_tmux(socket, session, line):
    return (
        subprocess.run(
            [
                "tmux",
                "-L",
                socket,
                "set-option",
                "-t",
                session,
                "status-format[0]",
                line,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
        ).returncode
        == 0
    )


def wait_for_refresh(seconds, socket=None, session=None):
    deadline = time.monotonic() + seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return True
        time.sleep(min(0.5, remaining))
        if socket and session and not tmux_session_exists(socket, session):
            return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--thread")
    parser.add_argument("--cwd", default=os.getcwd())
    parser.add_argument("--started-at", type=float)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--tmux-socket")
    parser.add_argument("--tmux-session")
    args = parser.parse_args()
    if args.thread and not re.fullmatch(r"[0-9a-fA-F-]{36}", args.thread):
        parser.error("Expected a thread UUID")
    if bool(args.tmux_socket) != bool(args.tmux_session):
        parser.error("--tmux-socket and --tmux-session must be used together")
    thread_id = args.thread
    while True:
        if args.tmux_session and not tmux_session_exists(
            args.tmux_socket, args.tmux_session
        ):
            return
        try:
            data = snapshot(thread_id, args.cwd, args.started_at)
            thread_id = data.get("_thread_id") or thread_id
            failure = False
        except Exception:
            data = {"cwd": args.cwd}
            failure = True
        text = (
            render_tmux(data)
            if args.tmux_session
            else render(data, color=os.isatty(1))
        )
        if failure:
            text += " · 조회 실패"
        if args.tmux_session:
            if not publish_tmux(args.tmux_socket, args.tmux_session, text):
                return
        elif args.watch:
            print("\033[?7l\r\033[2K" + text, end="", flush=True)
        else:
            print(text)
        if not args.watch:
            return
        if not wait_for_refresh(
            refresh_seconds(thread_id, data), args.tmux_socket, args.tmux_session
        ):
            return


if __name__ == "__main__":
    main()
