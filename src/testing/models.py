# Measurement, SamplingConfig, AnalysisResult(dataclasses only)

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


@dataclass(frozen=True)
class AnalysisResult:
    """
    The statistics for one run of one ammeter.

    Carries `ammeter_type` because the numbers are only meaningful next to the
    device that produced them - the three emulators read in different magnitudes.
    `standard_deviation` is None when a single sample makes it undefined; 0.0
    would claim perfect precision from one reading.
    """
    ammeter_type: str
    sample_count: int
    mean_current: float
    median_current: float
    standard_deviation: float | None
    min_current: float
    max_current: float

    def __str__(self) -> str:
        """
        A readable run summary. Values are formatted to six significant figures
        rather than a fixed number of decimals: the devices read three orders of
        magnitude apart, and `%.2f` would render every CIRCUTOR statistic as 0.01.
        """
        rows = [
            ("mean", self.mean_current),
            ("median", self.median_current),
            ("std dev", self.standard_deviation),
            ("min", self.min_current),
            ("max", self.max_current),
        ]

        lines = [f"{self.ammeter_type} - {self.sample_count} sample(s)"]

        for label, value in rows:
            # None only ever reaches here as the standard deviation at n=1.
            rendered = "n/a (needs 2+ samples)" if value is None else f"{value:.6g} A"
            lines.append(f"  {label:<8} {rendered}")

        return "\n".join(lines)


@dataclass(frozen=True)
class TestRunResult:
    """
    Represents a complete ammeter test run, including its configuration,
    collected measurements, analysis, and run metadata.
    """
    test_id: str
    ammeter_type: str
    started_at: datetime
    completed_at: datetime
    sampling_config: SamplingConfig
    measurements: list[Measurement]
    analysis: AnalysisResult


@dataclass(frozen=True)
class RunSummary:
    """
    One archived run reduced to the fields needed to choose between runs.

    Every value here was computed when the run was archived; nothing is
    recalculated from the raw samples. That keeps listing and comparison as
    pure presentation over stored metadata, and keeps new statistics out of
    the storage layer.
    """
    test_id: str
    ammeter_type: str
    started_at: datetime
    sample_count: int
    mean_current: float
    standard_deviation: float | None
    min_current: float
    max_current: float

    @classmethod
    def from_test_run(cls, result: TestRunResult) -> "RunSummary":
        """Project a loaded run onto its summary fields."""
        return cls(
            test_id=result.test_id,
            ammeter_type=result.ammeter_type,
            started_at=result.started_at,
            sample_count=result.analysis.sample_count,
            mean_current=result.analysis.mean_current,
            standard_deviation=result.analysis.standard_deviation,
            min_current=result.analysis.min_current,
            max_current=result.analysis.max_current,
        )
