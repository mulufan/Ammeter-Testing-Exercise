"""
The sampling loop and one complete run.

The only thing stubbed is `request_current_from_ammeter` - the single function
that touches a socket. Everything above it is exercised for real: the sampling
schedule, the per-sample error handling, the analysis, and the run's log file.
Substituting one function keeps the sockets out without turning the framework
into a puppet, which is what a mock of the framework's own methods would do.

`TestLogger`'s directory is redirected to `tmp_path` so a test run never writes
into the project's `results/logs/`.
"""

import pytest

from src.testing import test_framework as test_framework_module
from src.utils import logger as logger_module
from Ammeters.client import AmmeterConnectionError, AmmeterResponseError


@pytest.fixture
def stub_ammeter(monkeypatch, tmp_path):
    """
    Replace the socket call with a scripted sequence of readings.

    Each item is either a float to return or an exception to raise, so a test
    says what the device does by listing what comes back from it.
    """
    monkeypatch.setattr(logger_module, "LOG_DIR", tmp_path / "logs")

    def _stub(readings):
        remaining = list(readings)

        def _request(port, command):
            reading = remaining.pop(0)
            if isinstance(reading, Exception):
                raise reading
            return reading

        monkeypatch.setattr(
            test_framework_module, "request_current_from_ammeter", _request
        )

    return _stub


# 20 Hz over 3 samples is 0.1 s of wall clock - fast enough for a unit test,
# and still a real sleep between samples rather than a bypassed schedule.
FAST_SAMPLING = {"measurements_count": 3, "sampling_frequency_hz": 20.0}


def test_collect_samples_returns_one_measurement_per_configured_sample(
    make_framework, stub_ammeter
):
    stub_ammeter([1.0, 2.0, 3.0])
    framework = make_framework(**FAST_SAMPLING)

    measurements = framework.collect_samples("greenlee")

    assert [m.current for m in measurements] == [1.0, 2.0, 3.0]
    assert all(m.ammeter_type == "greenlee" for m in measurements)
    assert all(m.unit == "A" for m in measurements)


def test_an_unreadable_reply_is_skipped_and_sampling_continues(
    make_framework, stub_ammeter
):
    stub_ammeter([1.0, AmmeterResponseError("garbage reply"), 3.0])
    framework = make_framework(**FAST_SAMPLING)

    measurements = framework.collect_samples("greenlee")

    # One bad reply costs one sample, not the run.
    assert [m.current for m in measurements] == [1.0, 3.0]


def test_an_unreachable_device_aborts_the_run(make_framework, stub_ammeter):
    stub_ammeter([1.0, AmmeterConnectionError("connection refused")])
    framework = make_framework(**FAST_SAMPLING)

    # Deliberately not survivable: the remaining samples would all fail the same
    # way, and a run of two samples labelled as a run of three is a wrong answer.
    with pytest.raises(AmmeterConnectionError):
        framework.collect_samples("greenlee")


def test_an_unknown_device_is_rejected_before_any_socket_is_opened(make_framework):
    framework = make_framework(**FAST_SAMPLING)

    with pytest.raises(ValueError, match="Unsupported ammeter type"):
        framework.get_measurement("fluke")


def test_a_complete_run_carries_its_samples_statistics_and_metadata(
    make_framework, stub_ammeter, tmp_path
):
    stub_ammeter([1.0, 2.0, 3.0])
    framework = make_framework(**FAST_SAMPLING)

    result = framework.run_test("greenlee")

    assert result.ammeter_type == "greenlee"
    assert result.test_id
    assert result.started_at <= result.completed_at
    assert result.sampling_config.measurements_count == 3
    assert [m.current for m in result.measurements] == [1.0, 2.0, 3.0]
    assert result.analysis.sample_count == 3
    assert result.analysis.mean_current == 2.0

    # ISS-09: the supplied logger created the directory and wrote nothing.
    log_files = list((tmp_path / "logs").glob("*.log"))
    assert len(log_files) == 1
    log_text = log_files[0].read_text(encoding="utf-8")
    assert result.test_id in log_text


def test_a_failing_run_is_logged_and_the_error_propagates(
    make_framework, stub_ammeter, tmp_path
):
    stub_ammeter([AmmeterConnectionError("connection refused")])
    framework = make_framework(**FAST_SAMPLING)

    with pytest.raises(AmmeterConnectionError):
        framework.run_test("greenlee")

    # Logged where the context is known, then re-raised unchanged - the caller
    # decides what a failed run means.
    log_text = next((tmp_path / "logs").glob("*.log")).read_text(encoding="utf-8")
    assert "failed" in log_text
