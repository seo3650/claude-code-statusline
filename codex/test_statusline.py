import unittest
from statusline import render, metric, countdown, clean


class StatuslineTests(unittest.TestCase):
    def test_uniform_bar_and_thresholds(self):
        for value, color in [(59, "32"), (60, "33"), (84, "33"), (85, "31")]:
            text = metric("ctx", value)
            self.assertEqual(text.count("█"), 8)
            self.assertIn("\033[" + color + "m", text)

    def test_unknown_not_zero_and_expired_not_live(self):
        line = render(
            {"five_hour": {"used_percent": 90, "resets_at": 99, "observed_at": 100}},
            100,
            False,
        )
        self.assertNotIn("90%", line)
        self.assertNotIn("$?", line)
        self.assertNotIn("ctx", line)

    def test_countdown_parity(self):
        self.assertIn("(in 5d21h)", countdown(5 * 86400 + 21 * 3600, 0))
        self.assertIn("(in 4h11m)", countdown(4 * 3600 + 11 * 60, 0))
        self.assertIn("(in <1m)", countdown(30, 0))

    def test_terminal_injection_removed(self):
        self.assertNotIn("\033", clean("branch\033]52;payload\x07"))
        self.assertNotIn("\n", clean("branch\nnext"))


if __name__ == "__main__":
    unittest.main()
