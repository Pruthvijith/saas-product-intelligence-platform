from datetime import date, datetime, timedelta, timezone

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import os
from fastapi.testclient import TestClient
from pydantic import ValidationError

from product_intelligence.api import app
from product_intelligence.contracts import ProductEvent
from product_intelligence.experiment import assign, sample_ratio_p_value
from product_intelligence.metrics import activation_7d, exposure_counts, weekly_active_accounts
from product_intelligence.simulator import demo
from product_intelligence.store import connect, ingest, materialize_daily

START = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)


def event(event_id="e_01", name="signed_up", time=START, **extras):
    return ProductEvent(event_id=event_id, event_time=time, account_id="org_01",
                        user_id="user_01", event_name=name, **extras)


class PlatformTests(TestCase):
    def test_contract_rejects_naive_datetime_and_unknown_fields(self):
        with self.assertRaises(ValidationError):
            event(time=datetime(2026, 10, 1))
        with self.assertRaises(ValidationError):
            ProductEvent(**{**event().model_dump(), "email": "test@example.com"})

    def test_deduplicated_ingestion_and_late_partitions(self):
        tmp_path = Path(self.enterContext(TemporaryDirectory()))
        with connect(tmp_path / "db.sqlite") as db:
            assert ingest(db, event())
            assert not ingest(db, event())
            with self.assertRaisesRegex(ValueError, "Conflicting payload"):
                ingest(db, ProductEvent(**{**event().model_dump(), "account_id": "org_02"}))
            with self.assertRaises(ValueError):
                ingest(db, event("e_02", "feature_used"))
            assert ingest(db, event("e_03", "feature_used", feature_name="dashboard"))
            assert materialize_daily(db, "2026-10-01", "2026-10-03") == 1
            assert materialize_daily(db, "2026-10-01", "2026-10-03") == 1
            assert db.execute("SELECT feature_events FROM daily_account_usage").fetchone()[0] == 1
            assert ingest(db, event("e_04", "feature_used", feature_name="dashboard"))
            materialize_daily(db, "2026-10-01", "2026-10-03")
            assert db.execute("SELECT feature_events FROM daily_account_usage").fetchone()[0] == 2

    def test_activation_window_and_maturation(self):
        tmp_path = Path(self.enterContext(TemporaryDirectory()))
        with connect(tmp_path / "db.sqlite") as db:
            ingest(db, event())
            ingest(db, event("e_02", "onboarding_completed", START + timedelta(days=6)))
            assert activation_7d(db, date(2026, 10, 7))["eligible_users"] == 0
            assert activation_7d(db, date(2026, 10, 9))["rate"] == 1
            assert weekly_active_accounts(db, date(2026, 10, 9))["value"] == 0

    def test_stable_account_randomization_and_srm(self):
        assert assign("exp", "org", "salt") == assign("exp", "org", "salt")
        self.assertAlmostEqual(sample_ratio_p_value(100, 100), 1)
        assert sample_ratio_p_value(200, 20) < 1e-6

    def test_simulator_and_experiment(self):
        tmp_path = Path(self.enterContext(TemporaryDirectory()))
        path = str(tmp_path / "synthetic.sqlite")
        first = demo(path, accounts=80)
        second = demo(path, accounts=80)
        assert first["inserted"] > 0 and second["inserted"] == 0
        with connect(path) as db:
            metric = exposure_counts(db, "onboarding-v1")
            assert sum(metric["first_exposure_counts"].values()) == 80

    def test_http_idempotency(self):
        tmp_path = Path(self.enterContext(TemporaryDirectory()))
        self.enterContext(patch.dict(os.environ, PRODUCT_DB=str(tmp_path / "api.sqlite")))
        with TestClient(app) as client:
            data = event().model_dump(mode="json")
            assert client.post("/v1/events", json=data).json()["duplicate"] is False
            assert client.post("/v1/events", json=data).json()["duplicate"] is True
            assert client.get("/v1/metrics", params={"as_of": "2026-10-09"}).status_code == 200
