#!/usr/bin/env python3
"""Install only the explicit public code allowlist; preserve the original CLI link."""
from pathlib import Path
import os
import shutil
import uuid

FILES = [
    "statusline.py",
    "live.py",
    "launch.py",
    "rpc.py",
    "process_limits.py",
    "codex-launch",
]


def is_managed_entry(entry, real, source_launcher, current_install):
    if entry.is_symlink() and entry.resolve() == real.resolve():
        return True
    if not entry.is_file() or entry.is_symlink():
        return False
    deployed = entry.read_bytes()
    return deployed == source_launcher.read_bytes() or (
        current_install.is_file() and deployed == current_install.read_bytes()
    )


def main():
    source = Path(__file__).resolve().parent
    home = Path.home()
    real = home / ".codex/packages/standalone/current/bin/codex"
    entry = home / ".local/bin/codex"
    target = home / ".local/share/codex-statusline"
    if not real.is_file():
        raise SystemExit("Standalone Codex binary not found; install Codex first.")
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
            print("Original CLI link backed up:", backup)
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name in FILES:
        shutil.copy2(source / name, target / name)
    entry.parent.mkdir(parents=True, exist_ok=True)
    temporary = entry.with_name("codex.install-" + uuid.uuid4().hex)
    shutil.copy2(source / "codex-launch", temporary)
    temporary.chmod(0o755)
    os.replace(temporary, entry)
    (target / "codex-launch").chmod(0o755)
    print("Installed:", target)
    print(
        "The next codex process inherits a soft descriptor limit up to 4096; current sessions are unchanged."
    )


if __name__ == "__main__":
    main()
