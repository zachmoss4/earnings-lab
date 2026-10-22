from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo
import unittest

from earnings_lab.example import example_inputs
from earnings_lab.provider import fetch_inputs
from earnings_lab.engine import AnalysisError


class ProviderTests(unittest.TestCase):
    def stock(self, currency="USD"):
        inputs = example_inputs()
        today = datetime.now(ZoneInfo("America/New_York")).date()
        shifted = {(today + timedelta(days=(datetime.fromisoformat(day).date() - inputs.as_of).days)).isoformat(): frames for day, frames in inputs.chains.items()}
        return SimpleNamespace(options=tuple(shifted), history=lambda **kw: inputs.history,
                               option_chain=lambda day: SimpleNamespace(calls=shifted[day][0], puts=shifted[day][1]),
                               get_history_metadata=lambda: {"currency": currency, "longName": "Fixture Company"},
                               get_calendar=lambda: {"Earnings Date": [today + timedelta(days=2), today + timedelta(days=4)]})

    def test_date_ranges_remain_estimates_without_invented_session(self):
        with patch("earnings_lab.provider.yf.Ticker", return_value=self.stock()):
            result = fetch_inputs("AAPL")
        self.assertEqual(result.event["status"], "estimated")
        self.assertEqual(result.event["session"], "unknown")
        self.assertTrue(any(w["code"] == "event_range" for w in result.warnings))

    def test_non_usd_data_cannot_be_mislabeled_as_dollars(self):
        with patch("earnings_lab.provider.yf.Ticker", return_value=self.stock("CAD")):
            with self.assertRaisesRegex(AnalysisError, "USD"):
                fetch_inputs("TEST.TO")
