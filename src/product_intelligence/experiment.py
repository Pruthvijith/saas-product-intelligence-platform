"""Stable, reproducible A/B assignment and sample-ratio guardrail."""

import hashlib
import math


def assign(experiment: str, account_id: str, salt: str) -> str:
    if not experiment or not account_id or not salt:
        raise ValueError("All assignment fields required")
    # Randomization unit is account to avoid treatment contamination within an organization.
    digest = hashlib.sha256(f"{salt}:{experiment}:{account_id}".encode()).digest()
    return "control" if int.from_bytes(digest[:8], "big") < (1 << 63) else "treatment"


def sample_ratio_p_value(control: int, treatment: int) -> float:
    """Chi-square (df=1) 50:50 SRM approximation, two-sided tail."""
    if min(control, treatment) < 0 or control + treatment == 0:
        raise ValueError("Nonnegative observations required")
    expected = (control + treatment) / 2
    statistic = ((control - expected) ** 2 + (treatment - expected) ** 2) / expected
    return math.erfc(math.sqrt(statistic / 2))
