"""Exercise the complete demo in an isolated database."""
import json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from product_intelligence.cohorts import account_experiment, retention
from product_intelligence.metrics import activation_7d
from product_intelligence.simulator import demo
from product_intelligence.store import connect


def main() -> None:
    with TemporaryDirectory() as folder:
        path = str(Path(folder) / 'events.sqlite')
        first, replay = demo(path), demo(path)
        db = connect(path)
        try:
            as_of = date(2026, 10, 25)
            result = dict(first=first, replay=replay, activation=activation_7d(db, as_of),
                          retained=sum(r['retained_accounts'] for r in retention(db, as_of)),
                          experiment=account_experiment(db, as_of, 'onboarding-v1'))
        finally:
            db.close()
        assert replay['inserted'] == 0 and result['activation']['eligible_users'] == 240
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
