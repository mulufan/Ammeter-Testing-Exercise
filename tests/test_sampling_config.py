"""
Sampling configuration: deriving the missing parameter, and rejecting the
configurations that cannot describe a run.

The three parameters are over-determined - `count = duration x frequency + 1` -
so any two derive the third, and a contradictory trio is an error rather than a
precedence puzzle. These tests pin that rule down; it is the one piece of the
framework where a wrong answer is silent, because a bad config still produces
samples, just not the ones that were asked for.
"""

import pytest


def test_count_is_derived_from_duration_and_frequency(make_framework):
    framework = make_framework(total_duration_seconds=2.0, sampling_frequency_hz=2.0)

    config = framework._get_sampling_config()

    # 2 s at 2 Hz is 4 intervals, and a sample sits at both ends of each.
    assert config.measurements_count == 5
    assert config.total_duration_seconds == 2.0
    assert config.sampling_frequency_hz == 2.0


def test_derived_count_floors_and_recomputes_the_duration(make_framework):
    framework = make_framework(total_duration_seconds=2.7, sampling_frequency_hz=2.0)

    config = framework._get_sampling_config()

    # 2.7 s at 2 Hz is 5 whole intervals plus a remainder too short to hold a
    # sample. The count is floored to 6 and the duration is recomputed from it,
    # so the returned config describes the run that will actually happen - 2.5 s -
    # rather than echoing back the 2.7 s that was asked for.
    assert config.measurements_count == 6
    assert config.total_duration_seconds == 2.5


def test_duration_is_derived_from_count_and_frequency(make_framework):
    framework = make_framework(measurements_count=5, sampling_frequency_hz=2.0)

    config = framework._get_sampling_config()

    assert config.total_duration_seconds == 2.0


def test_frequency_is_derived_from_count_and_duration(make_framework):
    framework = make_framework(measurements_count=5, total_duration_seconds=2.0)

    config = framework._get_sampling_config()

    assert config.sampling_frequency_hz == 2.0


def test_all_three_are_accepted_when_they_agree(make_framework):
    framework = make_framework(
        measurements_count=5, total_duration_seconds=2.0, sampling_frequency_hz=2.0
    )

    config = framework._get_sampling_config()

    assert config.measurements_count == 5
    assert config.total_duration_seconds == 2.0
    assert config.sampling_frequency_hz == 2.0


def test_all_three_are_rejected_when_they_disagree(make_framework):
    framework = make_framework(
        measurements_count=5, total_duration_seconds=10.0, sampling_frequency_hz=2.0
    )

    with pytest.raises(ValueError, match="Inconsistent"):
        framework._get_sampling_config()


def test_one_parameter_is_not_enough(make_framework):
    framework = make_framework(measurements_count=5)

    with pytest.raises(ValueError, match="At least two"):
        framework._get_sampling_config()


def test_frequency_cannot_be_derived_from_a_single_measurement(make_framework):
    # count - 1 is zero intervals, so there is no rate to recover.
    framework = make_framework(measurements_count=1, total_duration_seconds=2.0)

    with pytest.raises(ValueError, match="cannot be derived"):
        framework._get_sampling_config()


@pytest.mark.parametrize(
    "parameters",
    [
        {"measurements_count": 0, "sampling_frequency_hz": 2.0},
        {"measurements_count": -5, "sampling_frequency_hz": 2.0},
        {"total_duration_seconds": 0, "sampling_frequency_hz": 2.0},
        {"measurements_count": 5, "sampling_frequency_hz": -2.0},
    ],
    ids=["zero-count", "negative-count", "zero-duration", "negative-frequency"],
)
def test_non_positive_parameters_are_rejected(make_framework, parameters):
    # These are the dangerous values: they survive the arithmetic and only
    # surface later as a ZeroDivisionError or an empty sample list.
    framework = make_framework(**parameters)

    with pytest.raises(ValueError):
        framework._get_sampling_config()


def test_a_fractional_count_is_rejected(make_framework):
    framework = make_framework(measurements_count=2.5, sampling_frequency_hz=2.0)

    with pytest.raises(ValueError, match="positive integer"):
        framework._get_sampling_config()
