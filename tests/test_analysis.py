"""
Statistics over a set of samples, and the precision ranking built on top of them.

Every case uses currents whose statistics are known by hand, so a failure means
the code is wrong rather than the expectation being re-derived from the code.
"""

import math

import pytest

from src.testing.models import AnalysisResult, PrecisionResult
from tests.conftest import make_measurements


# 1..5: mean 3, median 3, sample stdev sqrt(2.5).
KNOWN_CURRENTS = [1.0, 2.0, 3.0, 4.0, 5.0]


def test_statistics_over_known_values(make_framework):
    framework = make_framework(measurements_count=5, sampling_frequency_hz=2.0)

    analysis = framework.analyze_measurements(make_measurements(KNOWN_CURRENTS))

    assert analysis.ammeter_type == "greenlee"
    assert analysis.sample_count == 5
    assert analysis.mean_current == 3.0
    assert analysis.median_current == 3.0
    assert analysis.standard_deviation == pytest.approx(math.sqrt(2.5))
    assert analysis.min_current == 1.0
    assert analysis.max_current == 5.0


def test_standard_deviation_is_undefined_for_a_single_sample(make_framework):
    framework = make_framework(measurements_count=5, sampling_frequency_hz=2.0)

    analysis = framework.analyze_measurements(make_measurements([2.5]))

    # None, not 0.0: one reading cannot claim perfect precision.
    assert analysis.standard_deviation is None
    assert analysis.mean_current == 2.5


def test_an_empty_sample_list_is_rejected(make_framework):
    framework = make_framework(measurements_count=5, sampling_frequency_hz=2.0)

    with pytest.raises(ValueError, match="empty"):
        framework.analyze_measurements([])


def test_mixing_devices_in_one_analysis_is_rejected(make_framework):
    framework = make_framework(measurements_count=5, sampling_frequency_hz=2.0)

    # The three emulators read orders of magnitude apart, so a mean spanning
    # them describes no physical quantity at all.
    measurements = (
        make_measurements([1.0, 2.0], "greenlee")
        + make_measurements([100.0], "entes")
    )

    with pytest.raises(ValueError, match="same ammeter type"):
        framework.analyze_measurements(measurements)


def test_precision_is_the_coefficient_of_variation(make_framework):
    framework = make_framework(measurements_count=5, sampling_frequency_hz=2.0)

    analysis = framework.analyze_measurements(make_measurements(KNOWN_CURRENTS))
    precision = framework.evaluate_precision(analysis)

    assert precision.ammeter_type == "greenlee"
    assert precision.sample_count == 5
    assert precision.coefficient_of_variation == pytest.approx(math.sqrt(2.5) / 3.0)


@pytest.mark.parametrize(
    ("standard_deviation", "mean_current"),
    [(None, 2.5), (0.5, 0.0)],
    ids=["single-sample", "zero-mean"],
)
def test_coefficient_of_variation_is_undefined_where_it_has_no_meaning(
    make_framework, standard_deviation, mean_current
):
    framework = make_framework(measurements_count=5, sampling_frequency_hz=2.0)

    analysis = AnalysisResult(
        ammeter_type="greenlee",
        sample_count=5,
        mean_current=mean_current,
        median_current=mean_current,
        standard_deviation=standard_deviation,
        min_current=0.0,
        max_current=1.0,
    )

    assert framework.evaluate_precision(analysis).coefficient_of_variation is None


def _precision(ammeter_type, coefficient_of_variation):
    return PrecisionResult(
        ammeter_type=ammeter_type,
        sample_count=5,
        mean_current=1.0,
        standard_deviation=coefficient_of_variation,
        coefficient_of_variation=coefficient_of_variation,
    )


def test_ranking_puts_the_least_variable_first_and_the_undefined_last(make_framework):
    framework = make_framework(measurements_count=5, sampling_frequency_hz=2.0)

    ranked = framework.rank_precision([
        _precision("entes", 0.5),
        _precision("circutor", None),
        _precision("greenlee", 0.1),
    ])

    # The undefined one is kept, not dropped: a device that silently vanished
    # from the report would look like a device that was never sampled.
    assert [result.ammeter_type for result in ranked] == [
        "greenlee", "entes", "circutor"
    ]


def test_comparison_report_ranks_and_states_what_it_is_not(make_framework):
    framework = make_framework(measurements_count=5, sampling_frequency_hz=2.0)

    report = framework.compare_precision([
        _precision("entes", 0.5),
        _precision("greenlee", 0.1),
    ])

    lines = report.splitlines()
    assert lines[0].startswith("Ammeter")
    assert lines[2].startswith("greenlee")
    assert lines[3].startswith("entes")
    # The caveat is part of the result: a bare ranked table invites the reading
    # that the top row is the more accurate instrument, which these numbers
    # cannot establish.
    assert "not accuracy" in report


def test_comparing_nothing_is_an_error(make_framework):
    framework = make_framework(measurements_count=5, sampling_frequency_hz=2.0)

    with pytest.raises(ValueError, match="no precision results"):
        framework.compare_precision([])
