# SamplingConfig, Measurement (dataclasses only)

from dataclasses import dataclass, field
from datetime import datetime, timezone


def utc_now() -> datetime:
    """Timezone-aware capture time, so archived runs stay comparable across machines."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Measurement:
    """
    A single current reading from one ammeter.

    Frozen because a sample is a record of something that already happened;
    nothing downstream should be able to edit a reading after capture.
    A failed read is never represented here - the client raises instead.
    """
    ammeter_type: str
    current: float
    unit: str = "A"
    timestamp: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class SamplingConfig:
    """
    Represents the configuration for sampling measurements from ammeters.
    """
    measurements_count: int
    total_duration_seconds: float
    sampling_frequency_hz: float