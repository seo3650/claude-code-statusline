import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import install
import build_native


ROOT = Path(__file__).resolve().parent


class CodexLaunchTests(unittest.TestCase):
    def run_wrapper(self, patched_exists, *args):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            capture = root / "capture"
            official = root / "official"
            patched = root / "patched"
            script = '#!/bin/sh\nprintf \'%s\\n\' "$0" "$@" > "$CAPTURE"\n'
            official.write_text(script)
            official.chmod(0o755)
            if patched_exists:
                patched.write_text(script)
                patched.chmod(0o755)
            env = {
                **os.environ,
                "CAPTURE": str(capture),
                "CODEX_REAL_BIN": str(official),
                "CODEX_PATCHED_BIN": str(patched),
                "HOME": str(root),
            }
            completed = subprocess.run(
                [str(ROOT / "codex-launch"), *args],
                env=env,
                text=True,
                capture_output=True,
                timeout=5,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            return capture.read_text().splitlines(), patched, official

    def test_wrapper_runs_patched_binary_directly(self):
        lines, patched, _ = self.run_wrapper(True, "resume", "thread-id")
        self.assertEqual(lines, [str(patched), "resume", "thread-id"])

    def test_wrapper_falls_back_to_official_binary(self):
        lines, _, official = self.run_wrapper(False, "exec", "hello")
        self.assertEqual(lines, [str(official), "exec", "hello"])

    def test_wrapper_contains_no_tmux_runtime(self):
        self.assertNotIn("tmux", (ROOT / "codex-launch").read_text())


class InstallerTests(unittest.TestCase):
    def test_previous_installed_launcher_is_safe_to_upgrade(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            entry, real, source, previous = [
                root / name for name in ("entry", "real", "source", "previous")
            ]
            real.write_text("binary")
            source.write_text("new wrapper")
            previous.write_text("old wrapper")
            entry.write_text("old wrapper")
            self.assertTrue(install.is_managed_entry(entry, real, source, previous))

    def test_unrelated_custom_launcher_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            entry, real, source, previous = [
                root / name for name in ("entry", "real", "source", "previous")
            ]
            for path, text in [
                (entry, "custom"),
                (real, "binary"),
                (source, "new"),
                (previous, "old"),
            ]:
                path.write_text(text)
            self.assertFalse(install.is_managed_entry(entry, real, source, previous))

    def test_tui_merge_preserves_unrelated_configuration(self):
        original = (
            'model = "gpt-5"\n\n[tui]\nanimations = false\n\n'
            '[projects."/repo"]\ntrust_level = "trusted"\n'
        )
        merged = install.merge_tui_config(original)
        self.assertIn('model = "gpt-5"', merged)
        self.assertIn("animations = false", merged)
        self.assertIn('[projects."/repo"]', merged)
        self.assertEqual(merged.count("status_line ="), 1)
        self.assertIn("context-used-bar", merged)

    def test_tui_merge_is_idempotent(self):
        once = install.merge_tui_config("")
        self.assertEqual(install.merge_tui_config(once), once)


class NativeBundleTests(unittest.TestCase):
    def test_official_bundle_requires_matching_cli_and_host(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            bin_dir = home / ".codex/packages/standalone/current/bin"
            bin_dir.mkdir(parents=True)
            cli = bin_dir / "codex"
            host = bin_dir / "codex-code-mode-host"
            cli.write_text("#!/bin/sh\nprintf 'codex-cli %s\\n' '0.153.4'\n")
            cli.chmod(0o755)
            host.write_text("host")

            self.assertEqual(build_native.official_bundle(home), (cli, host))

    def test_official_bundle_rejects_missing_host(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            bin_dir = home / ".codex/packages/standalone/current/bin"
            bin_dir.mkdir(parents=True)
            cli = bin_dir / "codex"
            cli.write_text("#!/bin/sh\nexit 0\n")
            cli.chmod(0o755)

            with self.assertRaises(SystemExit):
                build_native.official_bundle(home)


if __name__ == "__main__":
    unittest.main()
