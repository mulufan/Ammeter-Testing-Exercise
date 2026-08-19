import math
import time

from typing import Dict

from Ammeters.client import request_current_from_ammeter
from src.testing.models import Measurement, SamplingConfig
from src.utils.config import load_config

from Ammeters.client import AmmeterConnectionError, AmmeterResponseError

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
        
    def run_test(self, ammeter_type: str) -> Dict:
        pass

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

    def collect_samples(self, ammeter_type: str) -> list[Measurement]:
        """
        Collect current measurements according to the configured sampling settings.
        Uses a monotonic clock to avoid timing drift between samples.
        """
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

            except AmmeterResponseError as exc:
                print(f"Skipping measurement due to ammeter response error: {exc}")
            except AmmeterConnectionError as exc:
                print(f"Aborting sampling due to ammeter connection error: {exc}")
                raise

        return measurements
        