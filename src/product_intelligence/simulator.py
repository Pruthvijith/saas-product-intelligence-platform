"""Synthetic deterministic clickstream with deliberate duplicate retries and late arrivals."""

import argparse
import random
from datetime import datetime, timedelta, timezone

from product_intelligence.contracts import ProductEvent
from product_intelligence.experiment import assign
from product_intelligence.store import connect, ingest, materialize_daily


def demo(db_path: str, accounts: int = 120, seed: int = 17) -> dict:
    rng = random.Random(seed)
    start = datetime(2026, 10, 1, 10, tzinfo=timezone.utc)
    inserted = duplicates = 0
    with connect(db_path) as db:
        for account_no in range(accounts):
            account = f"acct_{account_no:04d}"
            variant = assign("onboarding-v1", account, salt="demo-seed-v1")
            for user_no in range(2):
                user = f"user_{account_no:04d}_{user_no}"
                signup = start + timedelta(days=account_no % 10, minutes=user_no)
                rows = [ProductEvent(event_id=f"signup_{account_no}_{user_no}",
                                     event_time=signup, account_id=account, user_id=user,
                                     event_name="signed_up")]
                if rng.random() < (0.76 if variant == "treatment" else 0.65):
                    rows.append(ProductEvent(event_id=f"onboard_{account_no}_{user_no}",
                                             event_time=signup + timedelta(days=1),
                                             account_id=account, user_id=user,
                                             event_name="onboarding_completed"))
                if rng.random() < 0.8:
                    rows.append(ProductEvent(event_id=f"used_{account_no}_{user_no}",
                                             event_time=signup + timedelta(days=2),
                                             account_id=account, user_id=user,
                                             event_name="feature_used", feature_name="analytics_dashboard"))
                if rng.random() < 0.38:
                    rows.append(ProductEvent(event_id=f"repeat_{account_no}_{user_no}",
                                             event_time=signup + timedelta(days=9),
                                             account_id=account, user_id=user,
                                             event_name="feature_used", feature_name="roster"))
                for event in rows:
                    inserted += int(ingest(db, event))
                duplicates += int(not ingest(db, rows[0]))
            inserted += int(ingest(db, ProductEvent(event_id=f"exposed_{account_no}",
                                                    event_time=start +
                                                    timedelta(days=account_no % 10),
                                                    account_id=account, user_id=f"user_{account_no:04d}_0",
                                                    event_name="experiment_exposed", experiment_id="onboarding-v1",
                                                    variant=variant)))
        materialize_daily(db, "2026-10-01", "2026-10-31")
    return {"inserted": inserted, "retried_duplicates_ignored": duplicates,
            "source": "deterministic synthetic SaaS events"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="product_analytics.sqlite")
    parser.add_argument("--accounts", type=int, default=120)
    args = parser.parse_args()
    print(demo(args.db, accounts=args.accounts))


if __name__ == "__main__":
    main()
