"""Governed user/account KPI definitions with observation windows."""

import argparse
import json
import sqlite3
from datetime import date, timedelta

from product_intelligence.cohorts import account_experiment, retention
from product_intelligence.experiment import sample_ratio_p_value
from product_intelligence.store import connect


def activation_7d(db: sqlite3.Connection, as_of: date) -> dict:
    """Only mature signup cohorts have had a complete seven-day opportunity to activate."""
    cutoff = (as_of - timedelta(days=7)).isoformat()
    # First signup defines the cohort. Repeated client events do not inflate the denominator.
    rows = db.execute(
        """WITH signup AS (
             SELECT account_id,user_id, MIN(event_time) AS signed_at
             FROM raw_events WHERE event_name='signed_up'
             GROUP BY account_id,user_id
           ), activated AS (
             SELECT s.*, (SELECT min(e.event_time) FROM raw_events e
                 WHERE e.account_id=s.account_id AND e.user_id=s.user_id
                   AND e.event_name='onboarding_completed' AND e.event_time>=s.signed_at
                   AND julianday(e.event_time)<=julianday(s.signed_at)+7) AS completed_at
             FROM signup s WHERE date(s.signed_at)<=?
           )
           SELECT count(*) AS total, count(completed_at) AS activated,
             coalesce(sum(EXISTS(SELECT 1 FROM raw_events e WHERE
                e.account_id=a.account_id AND e.user_id=a.user_id AND e.event_name='feature_used'
                AND e.event_time>=a.completed_at
                AND julianday(e.event_time)<=julianday(a.signed_at)+7)),0) AS adopted
           FROM activated a""",
        (cutoff,),
    ).fetchone()
    return {"metric": "7d_user_activation", "as_of": as_of.isoformat(),
            "eligible_users": rows["total"], "activated_users": rows["activated"],
            "feature_users_after_activation": rows["adopted"],
            "rate": rows["activated"] / rows["total"] if rows["total"] else None}


def weekly_active_accounts(db: sqlite3.Connection, as_of: date) -> dict:
    start = (as_of - timedelta(days=6)).isoformat()
    row = db.execute(
        """SELECT COUNT(DISTINCT account_id) FROM raw_events
           WHERE event_name='feature_used' AND date(event_time) BETWEEN ? AND ?""",
        (start, as_of.isoformat()),
    ).fetchone()
    return {"metric": "weekly_active_accounts", "period_start": start,
            "period_end": as_of.isoformat(), "value": row[0]}


def exposure_counts(db: sqlite3.Connection, experiment_id: str) -> dict:
    """Deduplicate exposures to one record per account using earliest event."""
    rows = db.execute(
        """WITH ranked AS (
               SELECT account_id, variant,
                   ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY event_time,event_id) AS rn
               FROM raw_events WHERE event_name='experiment_exposed' AND experiment_id=?
           )
           SELECT variant, COUNT(*) AS n FROM ranked WHERE rn=1 GROUP BY variant""",
        (experiment_id,),
    ).fetchall()
    counts = {"control": 0, "treatment": 0}
    for row in rows:
        counts[row["variant"]] = row["n"]
    return {"experiment": experiment_id, "randomization_unit": "account",
            "first_exposure_counts": counts,
            "srm_p_value": sample_ratio_p_value(counts["control"], counts["treatment"])
            if sum(counts.values()) else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="product_analytics.sqlite")
    parser.add_argument("--rebuild-from", type=date.fromisoformat)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    with connect(args.db) as db:
        if args.rebuild_from:
            from product_intelligence.store import materialize_daily
            materialize_daily(db, args.rebuild_from.isoformat(), args.as_of.isoformat())
        print(json.dumps({"activation": activation_7d(db, args.as_of),
                          "waa": weekly_active_accounts(db, args.as_of),
                          "week_two": retention(db, args.as_of),
                          "experiment": account_experiment(db, args.as_of, "onboarding-v1")}, indent=2))


if __name__ == "__main__":
    main()
