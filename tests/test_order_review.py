import unittest
from datetime import date

from models import OptionQuote
from strategy import build_iron_condor
from order_review import build_review_payload, review_with_robinhood


class FakeRobinhoodMCP:
    def review_option_order(self, order):
        return {"status": "reviewed", "order": order}


class OrderReviewTests(unittest.TestCase):
    def setUp(self):
        expiration = date(2026, 10, 16)
        quotes = [
            OptionQuote("NDX", expiration, 24525, "put", 7.2, 7.6, -0.10),
            OptionQuote("NDX", expiration, 24550, "put", 8.8, 9.2, -0.12),
            OptionQuote("NDX", expiration, 24575, "put", 10.5, 11.0, -0.15),
            OptionQuote("NDX", expiration, 25225, "call", 10.3, 10.8, 0.15),
            OptionQuote("NDX", expiration, 25250, "call", 8.6, 9.0, 0.12),
            OptionQuote("NDX", expiration, 25275, "call", 7.0, 7.4, 0.10),
        ]
        self.condor = build_iron_condor(quotes, 0.10, 0.15, 25)

    def test_builds_four_leg_credit_payload(self):
        payload = build_review_payload(self.condor, quantity=2)
        self.assertEqual(payload["strategy"], "iron_condor")
        self.assertEqual(payload["quantity"], 2)
        self.assertEqual(payload["price_effect"], "credit")
        self.assertEqual(len(payload["legs"]), 4)
        self.assertEqual(payload["legs"][0]["side"], "buy")
        self.assertEqual(payload["legs"][1]["side"], "sell")
        self.assertEqual(payload["legs"][2]["side"], "sell")
        self.assertEqual(payload["legs"][3]["side"], "buy")

    def test_calls_review_not_place(self):
        result = review_with_robinhood(FakeRobinhoodMCP(), self.condor)
        self.assertEqual(result["status"], "reviewed")


if __name__ == "__main__":
    unittest.main()
