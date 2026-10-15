import contextlib
import io
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import main


class ReadOnlyStartupTests(unittest.TestCase):
    def test_read_only_does_not_construct_simulator_or_broker(self):
        settings = SimpleNamespace(trading_mode="read_only", robinhood_live_orders=False)
        with patch.object(main, "SETTINGS", settings), patch(
            "paper_market_data.PaperMarketDataProvider",
            side_effect=AssertionError("Simulator must not run"),
        ), patch(
            "broker_robinhood_mcp.RobinhoodMCPBroker",
            side_effect=AssertionError("Broker must not run"),
        ), contextlib.redirect_stdout(io.StringIO()) as output:
            main.main()
        self.assertIn("authentication is unverified", output.getvalue())

    def test_old_modes_fail_closed(self):
        for mode in ("paper", "invalid"):
            with self.subTest(mode=mode), patch.object(
                main, "SETTINGS",
                SimpleNamespace(trading_mode=mode, robinhood_live_orders=False),
            ), self.assertRaises(SystemExit):
                main.main()

    def test_live_flag_rejected(self):
        with patch.object(
            main, "SETTINGS",
            SimpleNamespace(trading_mode="read_only", robinhood_live_orders=True),
        ), self.assertRaises(SystemExit):
            main.main()

    def test_live_request_reports_transport_unavailable(self):
        with patch.object(
            main, "SETTINGS",
            SimpleNamespace(trading_mode="live", robinhood_live_orders=True),
        ), contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(
            SystemExit, "LIVE_UNAVAILABLE",
        ):
            main.main()
