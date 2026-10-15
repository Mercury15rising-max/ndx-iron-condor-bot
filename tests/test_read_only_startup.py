import contextlib
import io
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import main


class LiveStartupTests(unittest.TestCase):
    def test_non_live_modes_rejected(self):
        for mode in ("read_only", "paper", "invalid"):
            for flag in (False, True):
                with self.subTest(mode=mode, flag=flag), patch.object(
                    main, "SETTINGS",
                    SimpleNamespace(trading_mode=mode, robinhood_live_orders=flag),
                ), self.assertRaisesRegex(SystemExit, "Only live startup"):
                    main.main()

    def test_live_flag_required(self):
        with patch.object(
            main, "SETTINGS",
            SimpleNamespace(trading_mode="live", robinhood_live_orders=False),
        ), self.assertRaisesRegex(SystemExit, "requires ROBINHOOD_LIVE_ORDERS"):
            main.main()

    def test_live_request_reports_transport_unavailable(self):
        with patch.object(
            main, "SETTINGS",
            SimpleNamespace(trading_mode="live", robinhood_live_orders=True),
        ), contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(
            SystemExit, "LIVE_UNAVAILABLE",
        ):
            main.main()
