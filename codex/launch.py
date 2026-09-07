#!/usr/bin/env python3
"""Run Codex above a Claude-style one-row metrics pane."""
import argparse
from pathlib import Path
import re
import shlex
import subprocess
import time
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("thread", nargs="?", help="Existing Codex thread UUID")
    parser.add_argument(
        "--new",
        action="store_true",
        help="Start an interactive thread instead of resuming",
    )
    parser.add_argument("codex_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.new == bool(args.thread):
        parser.error("Choose exactly one of --new or an existing thread UUID")
    if args.thread and not re.fullmatch(r"[0-9a-fA-F-]{36}", args.thread):
        parser.error("Expected a thread UUID")
    root = Path(__file__).resolve().parent
    name = "codex-" + uuid.uuid4().hex[:10]
    prefix = ["tmux", "-L", "codex-statusline"]
    codex_args = args.codex_args
    if codex_args[:1] == ["--"]:
        codex_args = codex_args[1:]
    if not codex_args and args.thread:
        codex_args = ["resume", args.thread]
    if args.thread and codex_args[:2] != ["resume", args.thread]:
        parser.error("Codex arguments must resume the same thread UUID")
    started_at = time.time()
    inner_args = ["-c", "tui.status_line=[]", *codex_args]
    command = shlex.join(
        ["env", "CODEX_STATUSLINE_INNER=1", str(root / "codex-launch"), *inner_args]
    )
    subprocess.run(
        prefix + ["new-session", "-d", "-s", name, "-x", "160", "-y", "45", command],
        check=True,
    )
    try:
        subprocess.run(prefix + ["set-option", "-t", name, "status", "off"], check=True)
        footer_args = ["python3", str(root / "live.py"), "--cwd", str(Path.cwd())]
        if args.thread:
            footer_args += ["--thread", args.thread]
        else:
            footer_args += ["--started-at", str(started_at)]
        footer = shlex.join(footer_args + ["--watch"])
        subprocess.run(
            prefix + ["split-window", "-t", name + ":0", "-v", "-l", "1", footer],
            check=True,
        )
        subprocess.run(prefix + ["select-pane", "-t", name + ":0.0"], check=True)
    except Exception:
        subprocess.run(
            prefix + ["kill-session", "-t", name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        raise
    # Detaching keeps the session alive. Never kill a user's active Codex on detach.
    subprocess.run(prefix + ["attach-session", "-t", name], check=True)


if __name__ == "__main__":
    main()
