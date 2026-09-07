import os
from pathlib import Path
import tempfile
import time
import unittest

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


if __name__ == "__main__":
    unittest.main()
