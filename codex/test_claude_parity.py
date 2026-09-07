import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
from statusline import render


@unittest.skipUnless(
    shutil.which("jq") and shutil.which("git"),
    "jq/git required for original renderer parity",
)
class ClaudeParity(unittest.TestCase):
    def test_exact_ansi_output_with_synthetic_metrics(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            cwd = home / "myproject"
            cwd.mkdir()
            (home / ".claude").mkdir()
            subprocess.run(
                ["git", "init", "-b", "main", str(cwd)], check=True, capture_output=True
            )
            (cwd / "untracked-demo").write_text("synthetic")
            now = int(time.time())
            five = now + 270
            seven = now + 5 * 86400 + 21 * 3600 + 30
            source = {
                "model": {"display_name": "Codex", "id": "codex"},
                "workspace": {"current_dir": str(cwd)},
                "context_window": {"remaining_percentage": 64},
                "cost": {"total_cost_usd": 62.95},
                "effort": {"level": "xhigh"},
                "rate_limits": {
                    "five_hour": {"used_percentage": 66, "resets_at": five},
                    "seven_day": {"used_percentage": 36, "resets_at": seven},
                },
            }
            result = subprocess.run(
                ["bash", str(Path(__file__).resolve().parents[1] / "statusline.sh")],
                input=json.dumps(source),
                capture_output=True,
                text=True,
                env=dict(os.environ, HOME=folder),
                check=True,
            )
            data = dict(
                cwd="~/myproject",
                branch="main",
                dirty=True,
                context_percent=36,
                cost_usd=62.95,
                model="Codex",
                effort="xhigh",
                five_hour=dict(used_percent=66, resets_at=five, observed_at=now),
                seven_day=dict(used_percent=36, resets_at=seven, observed_at=now),
            )
            self.assertEqual(render(data, time.time()), result.stdout.rstrip("\n"))
