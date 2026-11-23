"""Account-level experiment readout and post-signup retention in event time."""

import math
import sqlite3
from datetime import date, timedelta

from product_intelligence.experiment import sample_ratio_p_value


def wilson(successes: int, total: int) -> tuple[float, float]:
    """95% Wilson score interval for a binomial proportion."""
    z = 1.959963984540054
    p = successes / total
    scale = 1 + z * z / total
    center = (p + z * z / (2 * total)) / scale
    width = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total**2)) / scale
    return max(0.0, center - width), min(1.0, center + width)


def account_experiment(db: sqlite3.Connection, as_of: date, experiment: str) -> dict:
    """One binary outcome per exposed account after a full seven days of follow-up."""
    until = (as_of + timedelta(days=1)).isoformat()
    rows = db.execute("""
        WITH exposures AS (
          SELECT account_id, variant, event_time, event_id,
            row_number() OVER (PARTITION BY account_id ORDER BY event_time,event_id) AS seq,
            min(variant) OVER (PARTITION BY account_id) AS first_label,
            max(variant) OVER (PARTITION BY account_id) AS last_label
          FROM raw_events WHERE event_name='experiment_exposed'
            AND experiment_id=? AND event_time < ?
        )
        SELECT variant, count(*) AS n, sum(first_label<>last_label) AS conflicts,
            sum(julianday(event_time)+7 <= julianday(?)) AS mature,
            sum(julianday(event_time)+7 <= julianday(?) AND EXISTS (
              SELECT 1 FROM raw_events e WHERE e.account_id=x.account_id
              AND e.event_name='onboarding_completed' AND e.event_time >= x.event_time
              AND julianday(e.event_time) < julianday(x.event_time)+7
            )) AS activated FROM exposures x WHERE seq=1 GROUP BY variant
        """, (experiment, until, until, until)).fetchall()
    arms = {v: dict(exposed=0, eligible=0, activated=0) for v in ('control', 'treatment')}
    conflicts = 0
    for row in rows:
        arms[row['variant']] = dict(
            exposed=row['n'], eligible=row['mature'], activated=row['activated'])
        conflicts += row['conflicts']
    c, t = arms.values()
    srm = sample_ratio_p_value(c['exposed'], t['exposed']) if rows else None
    interval = delta = None
    if c['eligible'] and t['eligible']:
        p, q = c['activated']/c['eligible'], t['activated']/t['eligible']
        lc, uc = wilson(c['activated'], c['eligible'])
        lt, ut = wilson(t['activated'], t['eligible'])
        delta = q - p
        interval = [delta - math.hypot(q-lt, uc-p), delta + math.hypot(ut-q, p-lc)]
    diagnostic = 'review_interval'
    if conflicts or srm is None or srm < 0.01 or min(c['eligible'], t['eligible']) < 20:
        diagnostic = 'hold_for_data_quality_or_sample'
    return dict(experiment=experiment, arms=arms, crossover_accounts=conflicts,
                srm_p_value=srm, absolute_rate_difference=delta, difference_ci95=interval,
                diagnostic=diagnostic)


def retention(db: sqlite3.Connection, as_of: date) -> list[dict]:
    """Return account-level week-two usage among fully observed signup cohorts."""
    return [dict(row) for row in db.execute("""
        WITH accounts AS (
          SELECT account_id,min(event_time) AS joined FROM raw_events
          WHERE event_name='signed_up' GROUP BY account_id
        )
        SELECT date(joined) AS signup_day,count(*) AS eligible_accounts,
          sum(EXISTS (SELECT 1 FROM raw_events e WHERE e.account_id=a.account_id
            AND e.event_name='feature_used'
            AND julianday(e.event_time)>=julianday(joined)+7
            AND julianday(e.event_time)<julianday(joined)+14)) AS retained_accounts
        FROM accounts a WHERE julianday(joined)+14 <= julianday(?)
        GROUP BY date(joined) ORDER BY signup_day
        """, ((as_of+timedelta(days=1)).isoformat(),))]
