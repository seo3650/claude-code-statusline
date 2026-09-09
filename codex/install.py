#!/usr/bin/env python3
"""Install the native Codex launcher and merge only its managed TUI settings."""

from pathlib import Path
import os
import re
import shutil
import uuid

FILES = [
    "build_native.py",
    "config.snippet.toml",
    "codex-launch",
    "patches/0.153.4-native-statusline.patch",
]
OBSOLETE_RUNTIME_FILES = [
    "launch.py",
    "live.py",
    "process_limits.py",
    "rpc.py",
    "statusline.py",
]
STATUS_LINE = (
    'status_line = ["current-dir", "git-branch", "context-used-bar", '
    '"five-hour-limit-bar", "weekly-limit-bar", "model", "reasoning"]'
)
COLORS = "status_line_use_colors = true"


def is_managed_entry(
    entry: Path, real: Path, source_launcher: Path, current_install: Path
) -> bool:
    if entry.is_symlink() and entry.resolve() == real.resolve():
        return True
    if not entry.is_file() or entry.is_symlink():
        return False
    deployed = entry.read_bytes()
    return deployed == source_launcher.read_bytes() or (
        current_install.is_file() and deployed == current_install.read_bytes()
    )


def merge_tui_config(text: str) -> str:
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == "[tui]"), None)
    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(["[tui]", STATUS_LINE, COLORS])
        return "\n".join(lines) + "\n"

    end = next(
        (i for i in range(start + 1, len(lines)) if re.match(r"^\s*\[", lines[i])),
        len(lines),
    )
    body = [
        line
        for line in lines[start + 1 : end]
        if not re.match(r"^\s*(status_line|status_line_use_colors)\s*=", line)
    ]
    lines[start + 1 : end] = [STATUS_LINE, COLORS, *body]
    return "\n".join(lines) + "\n"


def main() -> None:
    source = Path(__file__).resolve().parent
    home = Path.home()
    real = home / ".codex/packages/standalone/current/bin/codex"
    native = home / ".local/share/codex-statusline/bin/codex"
    native_host = native.parent / "codex-code-mode-host"
    entry = home / ".local/bin/codex"
    target = home / ".local/share/codex-statusline"
    if not real.is_file():
        raise SystemExit("Standalone Codex binary not found; install Codex first.")
    if not native.is_file():
        raise SystemExit("Patched Codex binary not found; run codex/build_native.py first.")
    if not native_host.is_file():
        raise SystemExit(
            "Code Mode host not found beside patched Codex; run codex/build_native.py first."
        )
    if entry.exists() or entry.is_symlink():
        if not is_managed_entry(
            entry, real, source / "codex-launch", target / "codex-launch"
        ):
            raise SystemExit(
                "Existing codex command is customized; preserved. Inspect it before installing."
            )
        if entry.is_symlink() and entry.resolve() == real.resolve():
            backup = home / ".local/share/codex-statusline-backups" / uuid.uuid4().hex
            backup.mkdir(parents=True, mode=0o700)
            shutil.copy2(entry, backup / "codex", follow_symlinks=False)

    for name in FILES:
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.copy2(source / name, destination)
    for name in OBSOLETE_RUNTIME_FILES:
        obsolete = target / name
        if obsolete.is_file() and not obsolete.is_symlink():
            obsolete.unlink()

    entry.parent.mkdir(parents=True, exist_ok=True)
    temporary = entry.with_name("codex.install-" + uuid.uuid4().hex)
    shutil.copy2(source / "codex-launch", temporary)
    temporary.chmod(0o755)
    os.replace(temporary, entry)
    (target / "codex-launch").chmod(0o755)

    config = home / ".codex/config.toml"
    config.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    current = config.read_text() if config.exists() else ""
    updated = merge_tui_config(current)
    if updated != current:
        temporary_config = config.with_name("config.toml.install-" + uuid.uuid4().hex)
        temporary_config.write_text(updated)
        temporary_config.chmod(0o600)
        os.replace(temporary_config, config)

    print(f"Installed native Codex statusline launcher: {entry}")
    print(f"Updated managed [tui] status_line settings: {config}")


if __name__ == "__main__":
    main()
