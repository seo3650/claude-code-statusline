#!/usr/bin/env python3
"""Build the pinned Codex CLI with the native bottom-pane statusline patch."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Dict, Optional

VERSION = "0.153.4"
TAG = f"rust-v{VERSION}"
UPSTREAM_COMMIT = "3d2ee51ca2d5db578f328aa75e20aa22c0197c9a"
UPSTREAM_URL = "https://github.com/openai/codex.git"


def run(*args: str, cwd: Optional[Path] = None, env: Optional[Dict[str, str]] = None) -> None:
    subprocess.run(args, cwd=cwd, env=env, check=True)


def verify_source(source: Path) -> None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=source,
        check=True,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip() != UPSTREAM_COMMIT:
        raise SystemExit(
            f"Expected Codex {TAG} at {UPSTREAM_COMMIT}; got a different source revision."
        )
    if subprocess.run(["git", "diff", "--quiet"], cwd=source).returncode != 0:
        raise SystemExit("Source checkout must be clean before applying the patch.")


def build(source: Path, patch: Path) -> Path:
    verify_source(source)
    run("git", "apply", "--check", str(patch), cwd=source)
    run("git", "apply", str(patch), cwd=source)
    env = {
        **os.environ,
        "CARGO_INCREMENTAL": "0",
        "CARGO_PROFILE_RELEASE_DEBUG": "0",
    }
    run(
        "cargo",
        "build",
        "--release",
        "-p",
        "codex-cli",
        "--bin",
        "codex",
        cwd=source / "codex-rs",
        env=env,
    )
    binary = source / "codex-rs" / "target/release/codex"
    if not binary.is_file():
        raise SystemExit("Codex release binary was not produced.")
    return binary


def copy_binary(binary: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = destination.with_name(destination.name + ".installing")
    shutil.copy2(binary, temporary)
    temporary.chmod(0o755)
    os.replace(temporary, destination)
    return destination


def official_bundle(home: Path) -> tuple[Path, Path]:
    """Return the matching official CLI and Code Mode host shipped together."""
    bin_dir = home / ".codex/packages/standalone/current/bin"
    cli = bin_dir / "codex"
    host = bin_dir / "codex-code-mode-host"
    if not cli.is_file() or not host.is_file():
        raise SystemExit(
            "Official standalone Codex bundle is incomplete; reinstall Codex first."
        )
    result = subprocess.run(
        [str(cli), "--version"],
        check=True,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip() != f"codex-cli {VERSION}":
        raise SystemExit(
            f"Official Code Mode host must come from Codex {VERSION}; "
            f"found {result.stdout.strip() or 'unknown version'}."
        )
    return cli, host


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        help="Clean Codex rust-v0.153.4 checkout. Omit to clone the pinned tag.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Copy the built binary here instead of installing it.",
    )
    args = parser.parse_args()

    patch = Path(__file__).resolve().parent / "patches/0.153.4-native-statusline.patch"
    if args.output:
        destination = args.output.expanduser().resolve()
    else:
        destination = Path.home() / ".local/share/codex-statusline/bin/codex"

    _, host = official_bundle(Path.home())
    if args.source:
        binary = build(args.source.resolve(), patch)
        destination = copy_binary(binary, destination)
    else:
        with tempfile.TemporaryDirectory(prefix="codex-statusline-build-") as folder:
            source = Path(folder) / "codex"
            run(
                "git",
                "clone",
                "--depth",
                "1",
                "--branch",
                TAG,
                UPSTREAM_URL,
                str(source),
            )
            binary = build(source, patch)
            destination = copy_binary(binary, destination)
    host_destination = copy_binary(
        host,
        destination.parent / "codex-code-mode-host",
    )
    print(f"Installed patched Codex {VERSION}: {destination}")
    print(f"Installed matching Code Mode host: {host_destination}")


if __name__ == "__main__":
    main()
