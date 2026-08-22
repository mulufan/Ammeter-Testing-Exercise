"""Shared helpers for the test suite.

Deliberately small. The framework's units are pure functions over plain data, so
the tests build that data directly instead of standing up sockets or patching the
client - see IMPLEMENTATION_NOTES.md, "Supporting work - the test suite".
"""

import statistics

import pytest

from src.testing.models import (
    AnalysisResult,
    Measurement,
    SamplingConfig,
    TestRunResult,
    utc_now,
)
from src.testing.test_framework import AmmeterTestFramework


@pytest.fixture
def make_framework(tmp_path):
    """
    Build a framework around a throwaway config file.

    Goes through the real constructor and the real YAML loader rather than
    assigning `.config` on an uninitialised instance: the sampling rules are read
    off `self.config`, and a hand-built dict would let a config-shape change pass
    the tests while breaking every run.
    """
    def _make(measurements_count=None, total_duration_seconds=None,
              sampling_frequency_hz=None):
        lines = ["testing:", "  sampling:"]
        for key, value in (
            ("measurements_count", measurements_count),
            ("total_duration_seconds", total_duration_seconds),
            ("sampling_frequency_hz", sampling_frequency_hz),
        ):
            # `null` keeps the key present, which is what the framework expects:
            # it counts how many are non-None, it does not use `.get()`.
            lines.append(f"    {key}: {'null' if value is None else value}")

        # One device is enough: the framework looks devices up by name in this
        # block, and nothing under test branches on which name it finds.
        lines += [
            "",
            "ammeters:",
            "  greenlee:",
            "    port: 5001",
            '    command: "MEASURE_GREENLEE -get_measurement"',
        ]

        config_path = tmp_path / "config.yaml"
        config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        return AmmeterTestFramework(str(config_path))

    return _make


def make_measurements(currents, ammeter_type="greenlee"):
    """Turn a list of known current values into samples from one device."""
    return [
        Measurement(ammeter_type=ammeter_type, current=current)
        for current in currents
    ]


def make_test_run(test_id="11111111-2222-3333-4444-555555555555",
                  ammeter_type="greenlee", currents=(1.0, 2.0, 3.0),
                  started_at=None):
    """A complete, self-consistent run for the storage round trip."""
    measurements = make_measurements(currents, ammeter_type)
    values = list(currents)
    # Passed in where a test needs two runs to be distinguishable by time:
    # utc_now() twice in a row can return the same value on a coarse clock.
    started_at = started_at if started_at is not None else utc_now()

    # Built here rather than by calling analyze_measurements, so a storage test
    # that fails points at storage and not at the analysis it borrowed.
    analysis = AnalysisResult(
        ammeter_type=ammeter_type,
        sample_count=len(values),
        mean_current=statistics.mean(values),
        median_current=statistics.median(values),
        standard_deviation=statistics.stdev(values) if len(values) > 1 else None,
        min_current=min(values),
        max_current=max(values),
    )

    return TestRunResult(
        test_id=test_id,
        ammeter_type=ammeter_type,
        started_at=started_at,
        completed_at=utc_now(),
        sampling_config=SamplingConfig(
            measurements_count=len(measurements),
            total_duration_seconds=2.0,
            sampling_frequency_hz=1.0,
        ),
        measurements=measurements,
        analysis=analysis,
    )
