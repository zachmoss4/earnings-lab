from pathlib import Path
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from earnings_lab.server import LabServer
from earnings_lab.example import example_inputs
from earnings_lab.engine import AnalysisError


class LocalFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.server = LabServer(("127.0.0.1", 0), Path(cls.temp.name))
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join()
        cls.temp.cleanup()

    def request(self, path, body=None, headers=None):
        request = urllib.request.Request(self.url + path, data=json.dumps(body).encode() if body is not None else None,
                                         headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as response:
            with response:
                return response.code, json.load(response)

    def test_example_save_list_and_reopen_are_consistent(self):
        with patch("earnings_lab.server.fetch_inputs", side_effect=AssertionError("Example must not use network")):
            status, result = self.request("/api/example")
        self.assertEqual(status, 200)
        self.assertEqual(result["source"], "example")
        status, saved = self.request("/api/snapshots", {"analysis_id": result["id"]})
        self.assertEqual(status, 201)
        self.assertTrue((Path(self.temp.name) / f"{result['id']}.json").exists())
        _, listing = self.request("/api/snapshots")
        self.assertTrue(any(item["id"] == result["id"] for item in listing))
        _, reopened = self.request(f"/api/snapshots/{result['id']}")
        self.assertEqual(reopened["metrics"], result["metrics"])
        self.assertEqual(reopened["retrieved_at"], result["retrieved_at"])
        self.assertEqual(reopened["saved_at"], saved["saved_at"])

    def test_analyze_passes_validated_inputs_and_caches_short_term(self):
        with patch("earnings_lab.server.fetch_inputs", return_value=example_inputs()) as fetch:
            first_status, first = self.request("/api/analyze", {"symbol": "MSFT"})
            second_status, second = self.request("/api/analyze", {"symbol": "MSFT"})
        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 200)
        self.assertEqual(first["id"], second["id"])
        fetch.assert_called_once_with("MSFT", None)

    def test_provider_failure_is_explicit_and_does_not_fall_back_to_fixture(self):
        with patch("earnings_lab.server.fetch_inputs", side_effect=AnalysisError("provider_unavailable", "Provider unavailable", 502)):
            status, result = self.request("/api/analyze", {"symbol": "FAIL"})
        self.assertEqual(status, 502)
        self.assertEqual(result["code"], "provider_unavailable")
        self.assertNotIn("metrics", result)

    def test_invalid_ticker_and_manual_date_rejected_before_network(self):
        with patch("earnings_lab.server.fetch_inputs") as fetch:
            for body in [{"symbol": "<script>"}, {"symbol": "AAPL", "event": {"date": "tomorrow"}}]:
                status, result = self.request("/api/analyze", body)
                self.assertIn(status, [400, 422])
                self.assertIn("error", result)
        fetch.assert_not_called()

    def test_other_web_origins_and_rebinding_hosts_are_rejected(self):
        for headers in [{"Origin": "https://example.com"}, {"Host": "attacker.example"}]:
            status, _ = self.request("/api/snapshots", {"analysis_id": "anything"}, headers)
            self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main()
