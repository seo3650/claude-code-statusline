import unittest
from unittest import mock

import launch


class StatusBarLifecycleTests(unittest.TestCase):
    @mock.patch("launch.subprocess.run")
    def test_status_bar_uses_no_footer_pane(self, run):
        prefix = ["tmux", "-L", "codex-statusline"]
        launch.configure_status_bar(prefix, "codex-test", "python3 live.py")
        commands = [call.args[0] for call in run.call_args_list]
        self.assertFalse(any("split-window" in command for command in commands))
        self.assertIn(
            prefix
            + [
                "run-shell",
                "-b",
                "-t",
                "codex-test:0.0",
                "python3 live.py",
            ],
            commands,
        )


if __name__ == "__main__":
    unittest.main()
