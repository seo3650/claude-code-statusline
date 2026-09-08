import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

import live


class ThreadDiscoveryTests(unittest.TestCase):
    def test_recent_thread_ids_exclude_old_files(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            sessions = home / "sessions" / "2026" / "09" / "07"
            sessions.mkdir(parents=True)
            recent_id = "11111111-2222-3333-4444-555555555555"
            old_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
            recent = sessions / f"rollout-now-{recent_id}.jsonl"
            old = sessions / f"rollout-old-{old_id}.jsonl"
            recent.touch()
            old.touch()
            started_at = time.time()
            os.utime(old, (started_at - 20, started_at - 20))
            previous = os.environ.get("CODEX_HOME")
            os.environ["CODEX_HOME"] = str(home)
            try:
                self.assertEqual(live._recent_thread_ids(started_at), [recent_id])
            finally:
                if previous is None:
                    os.environ.pop("CODEX_HOME", None)
                else:
                    os.environ["CODEX_HOME"] = previous

    def test_refresh_stays_fast_until_context_metric_arrives(self):
        thread = "11111111-2222-3333-4444-555555555555"
        self.assertEqual(live.refresh_seconds(thread, {"_thread_id": thread}), 2)
        self.assertEqual(live.refresh_seconds(thread, {"context_percent": 0}), 60)

    @mock.patch("live.tmux_session_exists", side_effect=[True, False])
    @mock.patch("live.time.sleep")
    @mock.patch("live.time.monotonic", side_effect=[0, 0, 0.5])
    def test_refresh_wait_stops_when_tmux_session_exits(
        self, _monotonic, _sleep, _session_exists
    ):
        self.assertFalse(live.wait_for_refresh(60, "socket", "session"))

    def test_tmux_renderer_uses_styles_and_escapes_format_injection(self):
        line = live.render_tmux(
            {"cwd": "~/repo", "branch": "#[bg=red]", "five_hour": {}}, now=100
        )
        self.assertNotIn("\033", line)
        self.assertIn("#[fg=", line)
        self.assertIn("##[bg=red]", line)


if __name__ == "__main__":
    unittest.main()
