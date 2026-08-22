"""
The measurement series plot.

Matplotlib's own rendering is not retested here - what matters is that a plot is
written where the archive expects it, named for the run, and that a run with
nothing to show refuses rather than saving empty axes.
"""

import dataclasses

import pytest

from src.testing.visualization import plot_measurement_series

from tests.conftest import make_test_run


def test_plot_is_saved_beside_the_run_under_the_same_test_id(tmp_path):
    result = make_test_run(currents=(1.0, 2.0, 3.0))

    file_path = plot_measurement_series(result, tmp_path)

    assert file_path == tmp_path / f"{result.test_id}.png"
    # A PNG, not a zero-byte file left behind by a failed save.
    assert file_path.read_bytes().startswith(b"\x89PNG")


def test_missing_output_directory_is_created(tmp_path):
    result = make_test_run()

    file_path = plot_measurement_series(result, tmp_path / "runs")

    assert file_path.exists()


def test_single_sample_run_still_plots(tmp_path):
    """n=1 leaves the standard deviation undefined; the series is still a series."""
    result = make_test_run(currents=(4.2,))

    assert plot_measurement_series(result, tmp_path).exists()


def test_run_without_measurements_is_rejected(tmp_path):
    result = dataclasses.replace(make_test_run(), measurements=[])

    with pytest.raises(ValueError, match="no measurements to plot"):
        plot_measurement_series(result, tmp_path)

    assert list(tmp_path.iterdir()) == []
