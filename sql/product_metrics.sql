-- Canonical example queries against the raw_events contract (SQLite dialect).
-- All timestamps are normalized UTC ISO strings at ingestion.

-- Daily active accounts for a named feature.
SELECT substr(event_time,1,10) AS event_day,
       feature_name,
       COUNT(DISTINCT account_id) AS active_accounts
FROM raw_events
WHERE event_name = 'feature_used'
GROUP BY event_day, feature_name
ORDER BY event_day, feature_name;

-- Ingestion quality: signal late-arrival risk relative to event time.
SELECT COUNT(*) AS received_events,
       COUNT(DISTINCT event_id) AS unique_events,
       MAX((julianday(ingested_at) - julianday(event_time)) * 24) AS max_lag_hours
FROM raw_events;

-- Enterprise reporting must parameterize tenant filters to avoid cross-tenant exposure.
SELECT COUNT(DISTINCT user_id) AS active_users
FROM raw_events
WHERE account_id = :account_id
  AND event_name = 'feature_used'
  AND event_time >= :window_start
  AND event_time < :window_end;
