import logging
import math
import time
import statistics
from uuid import uuid4

from Ammeters.client import request_current_from_ammeter
from Ammeters.client import AmmeterConnectionError, AmmeterResponseError

from src.utils.config import load_config
from src.utils.logger import TestLogger
from src.testing.models import (Measurement, SamplingConfig, AnalysisResult, TestRunResult, PrecisionResult, utc_now)



# Absolute tolerance for comparing configured and derived sampling parameters.
SAMPLING_TOLERANCE = 1e-9


def _validate_positive(name: str, value, integer: bool = False) -> None:
    """
    Reject a sampling parameter that cannot describe a run.
    Zero and negative values are the dangerous ones: they pass through the arithmetic
    below and only surface later, as a ZeroDivisionError or an empty sample list.
    """
    expected_type = int if integer else (int, float)

    # bool subclasses int, so `measurements_count: true` would otherwise be accepted as 1.
    if isinstance(value, bool) or not isinstance(value, expected_type):
        raise ValueError(
            f"{name} must be a positive {'integer' if integer else 'number'}, got {value!r}"
        )

    if value <= 0:
        raise ValueError(f"{name} must be greater than zero, got {value!r}")


class AmmeterTestFramework:
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config = load_config(config_path)

    def run_test(self, ammeter_type: str) -> TestRunResult:
        """
        Run one complete test against a device and return the archived result.

        The run writes its own log file under `results/logs/`, named for the device and
        the first octet of the run ID, so a run's console output, its JSON archive and
        its log can all be tied back to the same `test_id`.
        """
        ammeter_type = ammeter_type.lower()

        test_id = str(uuid4())
        started_at = utc_now()

        # The short ID keeps the filename readable while staying unique in practice;
        # the full ID is in the first line of the log itself.
        with TestLogger(f"{ammeter_type}_{test_id[:8]}") as logger:
            logger.info("Run %s started against %s", test_id, ammeter_type)

            try:
                sampling_config = self._get_sampling_config()
                logger.info(
                    "Sampling %d measurement(s) over %.6g s at %.6g Hz",
                    sampling_config.measurements_count,
                    sampling_config.total_duration_seconds,
                    sampling_config.sampling_frequency_hz,
                )

                measurements = self.collect_samples(ammeter_type, logger=logger)
                analysis = self.analyze_measurements(measurements)

            # Logged where the context is still known, then re-raised unchanged: the
            # caller's handling of a failed run is not this method's decision.
            except Exception as exc:
                logger.error("Run %s failed: %s: %s", test_id, type(exc).__name__, exc)
                raise

            completed_at = utc_now()

            logger.info(
                "Run %s completed: %d sample(s) in %.3f s",
                test_id,
                analysis.sample_count,
                (completed_at - started_at).total_seconds(),
            )
            # The statistics as they will be archived, so the log alone answers
            # "what did this run actually measure".
            logger.info("Statistics:\n%s", analysis)

        return TestRunResult(
        test_id=test_id,
        ammeter_type=ammeter_type,
        started_at=started_at,
        completed_at=completed_at,
        sampling_config=sampling_config,
        measurements=measurements,
        analysis=analysis,
    )

    def _get_sampling_config(self) -> SamplingConfig:
        """
        Validate the sampling configuration and derive the missing parameter
        when exactly two of count, duration, and frequency are provided.
        ```
        count = duration * frequency + 1
        duration = (count - 1) / frequency
        frequency = (count - 1) / duration
        nothing missing=>verify that all three agree
        ```
        The returned config always describes the run that will actually happen: a
        derived count is floored to whole sampling intervals, so the duration is
        recomputed from it rather than echoing back what was requested.
        """
        sampling = self.config["testing"]["sampling"]

        count = sampling["measurements_count"]
        duration = sampling["total_duration_seconds"]
        frequency = sampling["sampling_frequency_hz"]

        provided = sum(value is not None for value in (count, duration, frequency))

        if provided < 2:
            raise ValueError(
                "At least two sampling parameters must be configured."
            )

        # Only the configured values are checked; everything derived from them follows.
        if count is not None:
            _validate_positive("measurements_count", count, integer=True)

        if duration is not None:
            _validate_positive("total_duration_seconds", duration)

        if frequency is not None:
            _validate_positive("sampling_frequency_hz", frequency)

        if count is None:
            # Floored, so the run never overruns the requested duration. The tolerance
            # absorbs float representation error: 0.3 * 10 is 2.9999999999999996.
            intervals = math.floor(duration * frequency + SAMPLING_TOLERANCE)
            count = intervals + 1
            duration = intervals / frequency

        elif duration is None:
            duration = (count - 1) / frequency

        elif frequency is None:
            if count == 1:
                raise ValueError(
                    "sampling_frequency_hz cannot be derived from a single measurement; "
                    "configure it explicitly."
                )

            frequency = (count - 1) / duration

        else:
            expected_duration = (count - 1) / frequency

            if abs(expected_duration - duration) > SAMPLING_TOLERANCE:
                raise ValueError(
                    "Inconsistent sampling configuration: "
                    "measurements_count, total_duration_seconds, and "
                    "sampling_frequency_hz do not match."
                )

        return SamplingConfig(
            measurements_count=count,
            total_duration_seconds=duration,
            sampling_frequency_hz=frequency,
        )

    def get_measurement(self, ammeter_type: str) -> Measurement:
        """
        Retrieve a current measurement from the requested ammeter.
        Returns a unified result type so every ammeter reports the same way.
        Communication failures propagate as errors rather than as an empty reading.
        """
        ammeter_type = ammeter_type.lower()

        if ammeter_type not in self.config["ammeters"]:
            raise ValueError(f"Unsupported ammeter type: {ammeter_type}")

        ammeter_config = self.config["ammeters"][ammeter_type]

        port = ammeter_config["port"]
        command = ammeter_config["command"].encode("utf-8")

        current = request_current_from_ammeter(port, command)
        # Timestamp is taken here, as close to the reading as possible.
        return Measurement(ammeter_type=ammeter_type, current=current)

    def collect_samples(self, ammeter_type: str, logger=None) -> list[Measurement]:
        """
        Collect current measurements according to the configured sampling settings.
        Uses a monotonic clock to avoid timing drift between samples.

        `logger` accepts a `TestLogger` or a standard `logging.Logger`. Called directly
        without one, the messages go to a module logger that has no handler - silence,
        rather than the `print()` output this method used to interleave with results.
        """
        logger = logger if logger is not None else logging.getLogger(__name__)

        sampling_config = self._get_sampling_config()

        measurements = []
        period = 1 / sampling_config.sampling_frequency_hz

        start_time = time.monotonic()

        for index in range(sampling_config.measurements_count):
            target_time = start_time + (index * period)

            remaining_time = target_time - time.monotonic()

            if remaining_time > 0:
                time.sleep(remaining_time)

            try:
                measurement = self.get_measurement(ammeter_type)
                measurements.append(measurement)
                logger.debug(
                    "Sample %d/%d: %.6g A",
                    index + 1,
                    sampling_config.measurements_count,
                    measurement.current,
                )

            except AmmeterResponseError as exc:
                logger.warning(
                    "Sample %d/%d skipped, ammeter response error: %s",
                    index + 1,
                    sampling_config.measurements_count,
                    exc,
                )
            except AmmeterConnectionError as exc:
                logger.error("Sampling aborted, ammeter connection error: %s", exc)
                raise

        return measurements

    def analyze_measurements(self, measurements: list[Measurement]) -> AnalysisResult:
        """
        Calculate the required statistical metrics for a set of measurements.

        The samples must all come from one device: the three emulators read in
        different magnitudes, so a statistic spanning them describes nothing.
        The standard deviation is the sample one (n-1), and is None at n=1.
        """
        if not measurements:
            raise ValueError("Cannot analyze an empty measurement list.")

        ammeter_types = {measurement.ammeter_type for measurement in measurements}

        if len(ammeter_types) != 1:
            raise ValueError(
                "All measurements must be from the same ammeter type for analysis, "
                f"got {sorted(ammeter_types)}."
            )

        ammeter_type = next(iter(ammeter_types))
        current_values = [measurement.current for measurement in measurements]

        return AnalysisResult(
            ammeter_type=ammeter_type,
            sample_count=len(current_values),
            mean_current=statistics.mean(current_values),
            median_current=statistics.median(current_values),
            # Undefined for a single sample - see AnalysisResult.
            standard_deviation=(
                statistics.stdev(current_values) if len(current_values) > 1 else None
            ),
            min_current=min(current_values),
            max_current=max(current_values),
        )

    def evaluate_precision(self, analysis: AnalysisResult) -> PrecisionResult:
        """
        Evaluate the relative variability of one run using the coefficient of
        variation. A lower CV means the readings sat closer together relative to
        their own mean; it says nothing about how close they sat to the truth.

        Dividing by the mean is what makes the figure comparable at all here:
        the three devices read three orders of magnitude apart, so a raw standard
        deviation ranks them by magnitude rather than by consistency.

        The CV is left undefined at a zero mean, and at a single sample where
        there is no standard deviation to divide.
        """
        if analysis.standard_deviation is None or analysis.mean_current == 0:
            coefficient_of_variation = None
        else:
            coefficient_of_variation = (
                analysis.standard_deviation / abs(analysis.mean_current)
            )

        return PrecisionResult(
            ammeter_type=analysis.ammeter_type,
            sample_count=analysis.sample_count,
            mean_current=analysis.mean_current,
            standard_deviation=analysis.standard_deviation,
            coefficient_of_variation=coefficient_of_variation,
        )

    def rank_precision(
        self, precision_results: list[PrecisionResult]
    ) -> list[PrecisionResult]:
        """
        Order runs by relative variability, least variable first.

        Runs with no comparable CV are kept and sorted to the end rather than
        dropped. Discarding them would silently shrink the report - a device
        sampled once would simply not appear, with nothing in the output saying
        a device was missing.

        The first key element partitions the undefined ones out, so the second
        never has to discriminate within that group.
        """
        return sorted(
            precision_results,
            key=lambda result: (
                result.coefficient_of_variation is None,
                result.coefficient_of_variation or 0.0,
            ),
        )

    def compare_precision(self, precision_results: list[PrecisionResult]) -> str:
        """
        Render every device's relative variability as one ranked table.

        The closing note is part of the result, not decoration. Read bare, a
        ranked table headed by a device name invites the conclusion that the
        winner is the better instrument, which is exactly what these numbers
        cannot establish.
        """
        if not precision_results:
            raise ValueError("Nothing to compare: no precision results given.")

        ranked_results = self.rank_precision(precision_results)

        # Header and rows share these widths so the two cannot drift apart; they
        # were previously written out by hand and every column sat one character
        # off from the values underneath it.
        columns = (
            ("Ammeter", 11),
            ("Samples", 12),
            ("Mean (A)", 13),
            ("Std Dev", 12),
            ("CV (%)", 8),
        )

        lines = [
            "".join(title.ljust(width) for title, width in columns).rstrip(),
            "-" * sum(width for _, width in columns),
        ]

        for result in ranked_results:
            cells = (
                result.ammeter_type,
                str(result.sample_count),
                # Six significant figures, matching AnalysisResult.__str__: a
                # fixed decimal count renders every CIRCUTOR statistic as 0.01.
                format(result.mean_current, ".6g"),
                "N/A" if result.standard_deviation is None
                else format(result.standard_deviation, ".6g"),
                "N/A" if result.coefficient_of_variation is None
                else f"{result.coefficient_of_variation * 100:.2f}",
            )

            lines.append(
                "".join(
                    cell.ljust(width) for cell, (_, width) in zip(cells, columns)
                ).rstrip()
            )

        lines.append("")
        lines.append(
            "This ranks relative variability, not accuracy. The devices share no "
            "reference current, so there is no truth here to measure against and "
            "no device is shown to read correctly."
        )
        lines.append(
            "Each emulator also redraws its physical parameters on every call, so "
            "consecutive samples are independent draws rather than repeated reads "
            "of one current. These CVs describe the spread of each device's model, "
            "not the repeatability of an instrument."
        )
        lines.append(
            "A CV computed from few samples is itself unstable, and the ordering "
            "it produces can invert between runs. Raise the sample count before "
            "reading anything into a narrow gap."
        )

        return "\n".join(lines)
