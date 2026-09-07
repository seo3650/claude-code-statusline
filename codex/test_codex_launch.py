import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import install


ROOT = Path(__file__).resolve().parent


class CodexLaunchTests(unittest.TestCase):
    def run_wrapper(self, *args):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            statusline_home = root / "statusline"
            statusline_home.mkdir()
            capture = root / "capture"
            launcher = statusline_home / "launch.py"
            launcher.write_text(
                "import os, pathlib, sys\n"
                "pathlib.Path(os.environ['CAPTURE']).write_text('launcher\\n' + '\\n'.join(sys.argv[1:]))\n"
            )
            real = root / "real-codex"
            real.write_text(
                '#!/bin/sh\nprintf \'real\\n\' > "$CAPTURE"\nprintf \'%s\\n\' "$@" >> "$CAPTURE"\n'
            )
            real.chmod(0o755)
            master, slave = os.openpty()
            env = {
                **os.environ,
                "CAPTURE": str(capture),
                "CODEX_REAL_BIN": str(real),
                "CODEX_STATUSLINE_HOME": str(statusline_home),
                "HOME": str(root),
            }
            env.pop("TMUX", None)
            try:
                completed = subprocess.run(
                    [str(ROOT / "codex-launch"), *args],
                    stdin=slave,
                    stdout=slave,
                    stderr=subprocess.PIPE,
                    env=env,
                    text=True,
                    timeout=5,
                )
            finally:
                os.close(slave)
                os.close(master)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            return capture.read_text().splitlines()

    def test_plain_interactive_start_uses_statusline_launcher(self):
        self.assertEqual(self.run_wrapper(), ["launcher", "--new", "--"])

    def test_uuid_resume_uses_statusline_launcher(self):
        thread = "11111111-2222-3333-4444-555555555555"
        self.assertEqual(
            self.run_wrapper("resume", thread),
            ["launcher", thread, "--", "resume", thread],
        )

    def test_noninteractive_exec_bypasses_statusline_launcher(self):
        self.assertEqual(self.run_wrapper("exec", "hello"), ["real", "exec", "hello"])


class InstallerTests(unittest.TestCase):
    def test_previous_installed_launcher_is_safe_to_upgrade(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            entry = root / "entry"
            real = root / "real"
            source = root / "source"
            previous = root / "previous"
            real.write_text("binary")
            source.write_text("new wrapper")
            previous.write_text("old wrapper")
            entry.write_text("old wrapper")
            self.assertTrue(install.is_managed_entry(entry, real, source, previous))

    def test_unrelated_custom_launcher_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            entry = root / "entry"
            real = root / "real"
            source = root / "source"
            previous = root / "previous"
            for path, text in [
                (entry, "custom"),
                (real, "binary"),
                (source, "new wrapper"),
                (previous, "old wrapper"),
            ]:
                path.write_text(text)
            self.assertFalse(install.is_managed_entry(entry, real, source, previous))


if __name__ == "__main__":
    unittest.main()
