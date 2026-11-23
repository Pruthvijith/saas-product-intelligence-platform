"""Privacy-conscious v1 analytics tracking contract for a multi-tenant SaaS product."""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EventName(str, Enum):
    SIGNED_UP = "signed_up"
    ONBOARDING_DONE = "onboarding_completed"
    FEATURE_USED = "feature_used"
    EXPERIMENT_EXPOSED = "experiment_exposed"
    SUBSCRIPTION_STARTED = "subscription_started"


class ProductEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    event_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{3,80}$")
    event_time: datetime
    account_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{3,80}$")
    user_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{3,80}$")
    event_name: EventName
    feature_name: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")
    experiment_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")
    variant: str | None = Field(default=None, pattern=r"^(control|treatment)$")

    @field_validator("event_time")
    @classmethod
    def utc_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("event_time must have UTC offset")
        return value.astimezone(timezone.utc)

    @field_validator("feature_name", "experiment_id")
    @classmethod
    def nonempty_optional(cls, value):
        if value == "":
            raise ValueError("empty strings are not valid")
        return value

    def validate_semantics(self) -> None:
        if self.feature_name is not None and self.event_name != EventName.FEATURE_USED:
            raise ValueError("feature_name belongs only to feature_used")
        if self.event_name == EventName.FEATURE_USED and not self.feature_name:
            raise ValueError("feature_used requires feature_name")
        if self.event_name == EventName.EXPERIMENT_EXPOSED and not (self.experiment_id and self.variant):
            raise ValueError("experiment_exposed requires experiment_id and variant")
        if self.event_name != EventName.EXPERIMENT_EXPOSED and (self.experiment_id or self.variant):
            raise ValueError("experiment metadata belongs only to experiment_exposed")
