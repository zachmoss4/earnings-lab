import ast
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
import unittest
import numpy as np

from earnings_lab.engine import AnalysisError, analyze, classify, legacy_realized_volatility, selected_expiries
from earnings_lab.example import example_inputs


class EngineTests(unittest.TestCase):
    def test_original_volatility_formula_matches_preserved_source(self):
        source = Path(__file__).resolve().parents[1] / "reference/calculator.py"
        module = ast.parse(source.read_text())
        fn = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "yang_zhang")
        scope = {"np": np}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), str(source), "exec"), scope)
        history = example_inputs().history
        self.assertAlmostEqual(legacy_realized_volatility(history), scope["yang_zhang"](history), places=12)

    def test_interpolation_and_slope_have_explicit_units(self):
        result = analyze(example_inputs())
        expected_iv30 = .51 + (.465 - .51) * 6 / 7
        expected_iv45 = (.43 + .39) / 2
        self.assertAlmostEqual(result["metrics"]["iv30"], expected_iv30)
        self.assertAlmostEqual(result["metrics"]["slope_decimal_per_day"], (expected_iv45 - .86) / 42)
        self.assertAlmostEqual(result["metrics"]["expected_move_pct"], 6.66)
        self.assertEqual(result["classification"]["passed"], 3)

    def test_classification_all_eight_combinations(self):
        for volume in [False, True]:
            for ratio in [False, True]:
                for slope in [False, True]:
                    expected = "matches" if volume and ratio and slope else "partial" if slope and (volume or ratio) else "no_match"
                    self.assertEqual(classify(volume, ratio, slope)["key"], expected)

    def test_day45_only_rejected_instead_of_dividing_by_zero(self):
        day = date(2026, 10, 20)
        with self.assertRaisesRegex(AnalysisError, "before day 45"):
            selected_expiries([(day + timedelta(days=45)).isoformat()], day)

    def test_zeros_nan_crossed_quotes_and_strike_mismatch_are_rejected(self):
        for change in [{"bid": 0}, {"impliedVolatility": np.nan}, {"bid": 10}, {"strike": 105}]:
            inputs = example_inputs()
            first = next(iter(inputs.chains))
            for key, value in change.items():
                inputs.chains[first][0].loc[0, key] = value
            with self.assertRaises(AnalysisError):
                analyze(inputs)

    def test_bad_history_is_not_treated_as_a_failed_filter(self):
        for history in [example_inputs().history.head(10), example_inputs().history.assign(Close=0)]:
            inputs = example_inputs()
            inputs.history = history
            with self.assertRaises(AnalysisError):
                analyze(inputs)

    def test_event_after_front_expiry_is_flagged_separately(self):
        inputs = example_inputs()
        inputs.event["date"] = "2026-11-20"
        result = analyze(inputs)
        self.assertFalse(result["event"]["in_front_expiry"])
        self.assertEqual(result["classification"]["passed"], 3)
        self.assertTrue(any(w["code"] == "event_not_covered" for w in result["warnings"]))

    def test_calendar_quantity_basis_and_fixture_are_explicit(self):
        result = analyze(example_inputs())
        self.assertEqual(result["source"], "example")
        self.assertEqual(result["calendar"]["multiplier"], 100)
        self.assertEqual(result["calendar"]["gap_days"], 28)
        self.assertAlmostEqual(result["calendar"]["mid_debit"], 1.6)

    def test_invalid_optional_metadata_is_explicitly_unavailable(self):
        inputs = example_inputs()
        first = next(iter(inputs.chains))
        inputs.chains[first][0]["openInterest"] = np.inf
        inputs.chains[first][0]["lastTradeDate"] = "unavailable"
        result = analyze(inputs)
        self.assertIsNone(result["points"][0]["call"]["open_interest"])
        self.assertIsNone(result["points"][0]["call"]["last_trade_time"])
        self.assertTrue(any(w["code"] == "low_oi" for w in result["warnings"]))


if __name__ == "__main__":
    unittest.main()
