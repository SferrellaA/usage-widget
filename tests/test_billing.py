import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from datetime import datetime, timezone

from usage_widget.billing import (
    PUBLIC_KEYS,
    Unavailable,
    parse_billing,
    public_record,
    same_billing_host,
    write_status,
)

FIXTURE = {
    "subscription_tier": "SuperGrok",
    "config": {
        "currentPeriod": {
            "type": "USAGE_PERIOD_TYPE_WEEKLY",
            "end": "2026-11-09T21:39:21.847566+00:00",
        },
        "creditUsagePercent": 59.0,
        "productUsage": [
            {"product": "GrokBuild", "usagePercent": 43.0},
            {"product": "GrokChat", "usagePercent": 15.0},
        ],
    },
    "email": "should-not-leak@example.com",
    "key": "should-not-leak",
}


FRESH = {
    "subscription_tier": "SuperGrok",
    "config": {
        "currentPeriod": {
            "type": "USAGE_PERIOD_TYPE_WEEKLY",
            "start": "2026-11-02T21:39:21.847566+00:00",
            "end": "2026-11-09T21:39:21.847566+00:00",
        },
        "onDemandUsed": {"val": 0},
        "prepaidBalance": {"val": 0},
    },
}
NOW = datetime(2026, 11, 2, 22, 0, tzinfo=timezone.utc)


class BillingTests(unittest.TestCase):
    def test_parse_weekly_pool_not_product_split(self) -> None:
        record = parse_billing(FIXTURE)
        self.assertEqual(record["percentUsed"], 59.0)
        self.assertEqual(record["resetsAt"], "2026-11-09T21:39:21.847566+00:00")
        self.assertEqual(record["window"], "weekly")
        self.assertEqual(record["plan"], "SuperGrok")
        self.assertTrue(record["ok"])
        self.assertEqual(set(record), set(PUBLIC_KEYS))
        blob = json.dumps(record)
        self.assertNotIn("should-not-leak", blob)
        self.assertNotIn("GrokBuild", blob)
        self.assertNotIn("email", blob)

    def test_omitted_percent_on_a_new_window_is_zero(self) -> None:
        record = parse_billing(
            FRESH,
            now=NOW,
            previous_resets_at="2026-11-02T21:39:21.847566+00:00",
        )
        self.assertTrue(record["ok"])
        self.assertEqual(record["percentUsed"], 0.0)
        self.assertEqual(record["resetsAt"], "2026-11-09T21:39:21.847566+00:00")
        self.assertEqual(record["window"], "weekly")
        self.assertNotIn("onDemandUsed", json.dumps(record))

    def test_omitted_percent_on_the_same_window_is_not_zero(self) -> None:
        with self.assertRaises(Unavailable):
            parse_billing(
                FRESH,
                now=NOW,
                previous_resets_at="2026-11-09T21:39:21.847566+00:00",
            )

    def test_product_rows_do_not_stand_in_for_a_missing_pool(self) -> None:
        payload = json.loads(json.dumps(FRESH))
        payload["config"]["productUsage"] = [{"product": "GrokBuild", "usagePercent": 1.0}]
        with self.assertRaises(Unavailable):
            parse_billing(payload, now=NOW, previous_resets_at=None)

    def test_rejects_off_host_redirect(self) -> None:
        self.assertTrue(same_billing_host("https://cli-chat-proxy.grok.com/v1/billing"))
        self.assertFalse(same_billing_host("http://cli-chat-proxy.grok.com/v1/billing"))
        self.assertFalse(same_billing_host("https://evil.example/v1/billing"))
        self.assertFalse(same_billing_host("https://cli-chat-proxy.grok.com.evil.example/v1/billing"))

    def test_status_file_is_private_and_secret_free(self) -> None:
        record = public_record(ok=True, auth="ok", percent_used=12.0, resets_at="2026-11-09T00:00:00Z", window="weekly", plan="SuperGrok")
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "status.json"
            write_status(record, path)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(set(saved), set(PUBLIC_KEYS))


if __name__ == "__main__":
    unittest.main()
