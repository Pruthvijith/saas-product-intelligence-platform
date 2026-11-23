# Interview preparation · B2B SaaS product intelligence

Use first-person wording after you have run the demo and can explain or change the code yourself. Describe this as a portfolio implementation. Quantities below refer to the synthetic fixture.

## 30-second introduction

In this portfolio project I built a way for a SaaS product manager to decide whether to roll out guided onboarding. I tracked users for seven days and analyzed the experiment at the account level because coworkers share the experience. The synthetic treatment group was ahead by about one percentage point, but the interval included meaningful harm and benefit. I would wait before expanding the rollout.

## Two-minute technical explanation

Start at contracts.py and store.py. An event carries an immutable event ID and an offset-aware timestamp. Ingest normalizes to UTC and compares attempted duplicate payloads. Metrics join first signup to subsequent completion within the account. Cohorts.py builds account exposure windows, flags crossed variants and calculates uncertainty. The as-of date is an event-time cutoff, so a historical replay can legitimately revise a previous number.

The ordered user funnel counts signup, first qualifying completion and subsequent meaningful use within the same seven-day signup window. A signup is unique per account and user. Weekly active accounts count a meaningful feature event in the last seven UTC dates. Week-two retention counts accounts with activity in days 7–13 after their first signup. The experiment counts any onboarding completion within seven days of first exposure, once per account. It reports a Newcombe difference interval from two Wilson score intervals. Replay corrects historical event-time results, so archive each decision readout when an as-known-at snapshot is required.

Across 120 synthetic accounts, 168 of 240 users completed onboarding within seven days. At the randomized account grain, 54/61 control and 53/59 treatment accounts activated. The difference was +1.31 percentage points, with a 95% interval from −10.51 to +13.01 points. **Defer rollout on this evidence.**

The account outcome can increase when tenants have more users. The demo generates two users per account. It does not measure churn, support burden or sustained causal impact. An identity policy and authenticated, tenant-scoped reads would be prerequisites for customer access.

## Architecture walkthrough

Open the files in this order and follow one record through the system.

[contracts.py](../src/product_intelligence/contracts.py) · [store.py](../src/product_intelligence/store.py) · [cohorts.py](../src/product_intelligence/cohorts.py) · [metrics.py](../src/product_intelligence/metrics.py)

Start at contracts.py and store.py. An event carries an immutable event ID and an offset-aware timestamp. Ingest normalizes to UTC and compares attempted duplicate payloads. Metrics join first signup to subsequent completion within the account. Cohorts.py builds account exposure windows, flags crossed variants and calculates uncertainty. The as-of date is an event-time cutoff, so a historical replay can legitimately revise a previous number.

## Five technical questions

**1. Why use an account for randomization?**

Colleagues can influence each other. Assignment and the binary experiment outcome both use the account, which avoids treating coworkers as independent trials.

**2. What does a retry change?**

An identical event ID and payload returns a duplicate acknowledgement. A changed payload with the same ID is rejected.

**3. Can a later exposure change an earlier readout?**

A later event time is excluded from the earlier cutoff. A late delivery with an earlier event time can revise it. The system stores event and ingestion time.

**4. How are windows bounded?**

User activation includes the seven-day boundary. The account exposure outcome and week-two retention use half-open time windows. The distinction is recorded because the metrics answer different questions.

**5. Why can the two conversion rates differ?**

The experiment counts whether any member activated. The user metric counts every eligible member. Both denominators are exposed in outputs.

## Five product and business questions

**1. What constitutes first value?**

A server-confirmed onboarding milestone. Validate with customer interviews whether it predicts a successful first schedule.

**2. Would you ship?**

The estimate is +1.31 points and the interval spans zero. Continue a pre-specified trial with adequate power.

**3. Why keep retention separate?**

It tests whether accounts return to a meaningful feature after the onboarding window.

**4. Which guardrail could overturn a positive result?**

An increase in support contacts or churn could outweigh faster onboarding. Those outcomes need additional instrumentation.

**5. What would you cut first?**

A dashboard redesign can wait until event identity and cohort definitions agree across teams.

## What to demonstrate live

Run `python scripts/demo.py`. Point to one input, the relevant transformation and the output that supports your decision. Move a completion just outside the seven-day window. Predict which account and user counts will change, then add a boundary test.

## Main trade-off and next test

FastAPI validates incoming events, Pydantic restricts their schema, and SQLite supports indexed reads and atomic partition rebuilds. A warehouse and broker become useful once concurrent writers or event history exceed what one host can accommodate.

The account outcome can increase when tenants have more users. The demo generates two users per account. It does not measure churn, support burden or sustained causal impact. An identity policy and authenticated, tenant-scoped reads would be prerequisites for customer access.

## CV wording for a portfolio section

- Built a synthetic B2B SaaS analytics service with idempotent event ingestion, seven-day activation, week-two retention and account-level experiment readouts across 120 simulated tenants.
