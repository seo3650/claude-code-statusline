import subprocess
import unittest
from unittest import mock

import launch


class PaneLifecycleTests(unittest.TestCase):
    @mock.patch("launch.subprocess.run")
    def test_pane_id_rejects_untrusted_tmux_output(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, stdout="unexpected\n")
        with self.assertRaisesRegex(RuntimeError, "invalid pane id"):
            launch.pane_id(["tmux", "-L", "test"], "session:0.0")

    @mock.patch("launch.subprocess.run")
    def test_primary_exit_hook_kills_only_footer_pane(self, run):
        prefix = ["tmux", "-L", "codex-statusline"]
        launch.install_exit_hook(prefix, "codex-test", "%12", "%13")
        run.assert_called_once_with(
            prefix
            + [
                "set-hook",
                "-t",
                "codex-test",
                "pane-exited",
                "if-shell -F '#{==:#{hook_pane},%12}' 'kill-pane -t %13' ''",
            ],
            check=True,
        )


if __name__ == "__main__":
    unittest.main()
