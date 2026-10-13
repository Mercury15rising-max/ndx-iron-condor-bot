import unittest
from unittest.mock import patch

import automation_runner


class AutomationRunnerSafetyTests(unittest.TestCase):
    def test_module_defaults_to_safe_poll_interval(self):
        self.assertGreaterEqual(automation_runner.POLL_SECONDS, 30)

    def test_runner_module_has_main(self):
        self.assertTrue(callable(automation_runner.main))


if __name__ == "__main__":
    unittest.main()
