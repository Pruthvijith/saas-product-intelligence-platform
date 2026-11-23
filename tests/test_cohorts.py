from datetime import date, timedelta
from unittest import TestCase

from product_intelligence.cohorts import account_experiment, retention
from product_intelligence.metrics import activation_7d
from product_intelligence.store import connect, ingest
from test_product_intelligence import START, event


class CohortTests(TestCase):
    def setUp(self):
        self.db = connect(":memory:")
        self.addCleanup(self.db.close)
        ingest(self.db, event())
        self.expose('exp1', 'control', 0)

    def expose(self, key, arm, day):
        ingest(self.db, event(key, 'experiment_exposed', START+timedelta(days=day),
                              experiment_id='trial', variant=arm))

    def test_maturity_crossover_and_pre_exposure_outcome(self):
        ingest(self.db, event('old', 'onboarding_completed', START-timedelta(seconds=1)))
        self.expose('exp2', 'treatment', 9)
        early = account_experiment(self.db, date(2026, 10, 6), 'trial')
        self.assertEqual(early['arms']['control']['eligible'], 0)
        self.assertEqual(early['crossover_accounts'], 0)
        final = account_experiment(self.db, date(2026, 10, 20), 'trial')
        self.assertEqual(final['arms']['control'], dict(exposed=1, eligible=1, activated=0))
        self.assertEqual(final['crossover_accounts'], 1)
        self.assertIsNone(final['difference_ci95'])

    def test_retention_excludes_day_fourteen_and_immature_cohorts(self):
        ingest(self.db, event('too_late', 'feature_used',
               START+timedelta(days=14), feature_name='plan'))
        self.assertEqual(retention(self.db, date(2026, 10, 10)), [])
        end = date(2026, 10, 20)
        self.assertEqual(retention(self.db, end)[0]['retained_accounts'], 0)
        ingest(self.db, event('week_two', 'feature_used', START+timedelta(days=7), feature_name='plan'))
        self.assertEqual(retention(self.db, end)[0]['retained_accounts'], 1)

    def test_funnel_requires_order_and_preserves_tenant_identity(self):
        second_signup = event("second").model_copy(update={"account_id": "org_02"})
        ingest(self.db, second_signup)
        ingest(self.db, event("early", "feature_used", START, feature_name="roster"))
        ingest(self.db, event("done", "onboarding_completed", START + timedelta(days=1)))
        cutoff = date(2026, 10, 15)
        m = activation_7d(self.db, cutoff)
        self.assertEqual((m["eligible_users"], m["activated_users"],
                         m["feature_users_after_activation"]), (2, 1, 0))
        ingest(self.db, event("other", "feature_used", START+timedelta(days=2), feature_name="roster")
               .model_copy(update={"account_id": "org_02"}))
        self.assertEqual(activation_7d(self.db, cutoff)["feature_users_after_activation"], 0)
        ingest(self.db, event("ordered", "feature_used",
               START+timedelta(days=2), feature_name="roster"))
        self.assertEqual(activation_7d(self.db, cutoff)["feature_users_after_activation"], 1)
