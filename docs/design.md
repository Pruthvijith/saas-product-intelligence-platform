# Product requirements and operating notes

## User decision and opportunity

A product manager needs to decide whether guided onboarding helps new accounts reach first value. This service turns retry-prone product events into a rollout readout with a defined denominator and a measure of uncertainty.

| Stakeholder | Priority and milestone | Acceptance criterion |
|---|---|---|
| Product owner | P0 · rollout readout | Show numerator, denominator, observation end and confidence interval. Hold if a crossover, imbalance flag or small-sample gate fires. |
| Analytics engineer | P0 · trustworthy inputs | Reject ambiguous retries. Reprocessing a range must preserve counts in the absence of new events. |
| Customer success | P1 · adoption diagnosis | Compare signup cohorts and week-two use. An account with no qualifying action contributes zero. |

## Metric definitions and validation

The ordered user funnel counts signup, first qualifying completion and subsequent meaningful use within the same seven-day signup window. A signup is unique per account and user. Weekly active accounts count a meaningful feature event in the last seven UTC dates. Week-two retention counts accounts with activity in days 7–13 after their first signup. The experiment counts any onboarding completion within seven days of first exposure, once per account. It reports a Newcombe difference interval from two Wilson score intervals. Replay corrects historical event-time results, so archive each decision readout when an as-known-at snapshot is required.

Across 120 synthetic accounts, 168 of 240 users completed onboarding within seven days. At the randomized account grain, 54/61 control and 53/59 treatment accounts activated. The difference was +1.31 percentage points, with a 95% interval from −10.51 to +13.01 points. **Defer rollout on this evidence.**

## Architecture decision record

**Accepted for this local workload.** FastAPI validates incoming events, Pydantic restricts their schema, and SQLite supports indexed reads and atomic partition rebuilds. A warehouse and broker become useful once concurrent writers or event history exceed what one host can accommodate.

Start at contracts.py and store.py. An event carries an immutable event ID and an offset-aware timestamp. Ingest normalizes to UTC and compares attempted duplicate payloads. Metrics join first signup to subsequent completion within the account. Cohorts.py builds account exposure windows, flags crossed variants and calculates uncertainty. The as-of date is an event-time cutoff, so a historical replay can legitimately revise a previous number.

The implementation lives in [the Python package](../src/product_intelligence). The boundaries are exercised by [the test suite](../tests).

## Operating procedure

The local API uses a single SQLite writer and exposes aggregate metrics to its operator. Bind to loopback. For a delayed event, insert it with the original event time and run `product-metrics --db product_analytics.sqlite --rebuild-from 2026-10-01 --as-of 2026-10-25`. Duplicate IDs with different payloads fail. Keep the raw log and rebuild the affected dates. Proposed operational target for a pilot: a successful daily close with all known partitions present.

1. Reproduce the baseline with `python scripts/demo.py`. Compare the decision fields with the committed example.
2. Run the regression suite before changing input definitions or thresholds. Use the persistent example in the README to inspect intermediate state.
3. Run `python scripts/http_smoke.py` to test the API over TCP. The server exits at the end of the check.

### Container example

From the repository root:

```shell
docker compose up --build
```

The Compose port is bound to loopback.
This configuration awaits Docker execution. The same demo was exercised with the installed Python package.

## Constraints, reliability and delivery

The account outcome can increase when tenants have more users. The demo generates two users per account. It does not measure churn, support burden or sustained causal impact. An identity policy and authenticated, tenant-scoped reads would be prerequisites for customer access.

First instrument server-confirmed signup, exposure and completion. Next validate idempotency and cohort boundaries. Then read the synthetic trial at a fixed horizon. A follow-up pilot would pre-register an effect size, account-level power and churn guardrails.

Local demo data and code are independent of former employers. Cost scenarios use declared assumptions. Operational targets describe a proposed pilot.
