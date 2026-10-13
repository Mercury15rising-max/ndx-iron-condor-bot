import unittest

from exit_manager import evaluate_exit


class ExitManagerTests(unittest.TestCase):
    def test_take_profit(self):
        decision = evaluate_exit(
            entry_credit=5.00,
            current_debit_to_close=2.50,
            profit_target_pct=50,
            stop_loss_multiple=2.0,
        )
        self.assertEqual(decision.action, "take_profit")

    def test_stop_loss(self):
        decision = evaluate_exit(
            entry_credit=5.00,
            current_debit_to_close=10.00,
            profit_target_pct=50,
            stop_loss_multiple=2.0,
        )
        self.assertEqual(decision.action, "stop_loss")

    def test_time_exit(self):
        decision = evaluate_exit(
            entry_credit=5.00,
            current_debit_to_close=4.00,
            profit_target_pct=50,
            stop_loss_multiple=2.0,
            minutes_to_close=20,
            time_exit_minutes=30,
        )
        self.assertEqual(decision.action, "time_exit")

    def test_kill_switch(self):
        decision = evaluate_exit(
            entry_credit=5.00,
            current_debit_to_close=4.00,
            profit_target_pct=50,
            stop_loss_multiple=2.0,
            daily_realized_pnl=-800,
            max_daily_loss=750,
        )
        self.assertEqual(decision.action, "kill_switch")


if __name__ == "__main__":
    unittest.main()
