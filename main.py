import argparse
import math
import threading
import time

from src.testing.test_framework import AmmeterTestFramework
from src.testing.result_manager import (
    ResultStoreError,
    compare_test_runs,
    list_test_runs,
    load_test_run,
    save_test_run,
)
from src.testing.visualization import plot_measurement_series

from Ammeters.Circutor_Ammeter import CircutorAmmeter
from Ammeters.Entes_Ammeter import EntesAmmeter
from Ammeters.Greenlee_Ammeter import GreenleeAmmeter
from Ammeters.client import AmmeterError

DEFAULT_INTERVAL_SECONDS = 15.0
EMULATOR_STARTUP_SECONDS = 5


def run_greenlee_emulator():
    greenlee = GreenleeAmmeter(5001)
    greenlee.start_server()

def run_entes_emulator():
    entes = EntesAmmeter(5002)
    entes.start_server()

def run_circutor_emulator():
    circutor = CircutorAmmeter(5003)
    circutor.start_server()


def parse_args():
    """Command line options. Without one of these, a plain run happens."""
    parser = argparse.ArgumentParser(
        description="Sample the ammeters, or read archived runs back."
    )

    # Mutually exclusive: each one is a different report over the same archive.
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--list", action="store_true", help="list archived runs, oldest first"
    )
    group.add_argument(
        "--show", metavar="TEST_ID", help="show one archived run in full"
    )
    group.add_argument(
        "--compare",
        metavar="TEST_ID",
        nargs="+",
        help="compare archived runs side by side",
    )

    parser.add_argument(
        "--monitor",
        action="store_true",
        help="run continuously and export Prometheus metrics on /metrics",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL_SECONDS,
        metavar="SECONDS",
        help=f"seconds between monitor cycles (default: {DEFAULT_INTERVAL_SECONDS})",
    )

    return parser.parse_args()


def list_runs():
    """Print one line per archived run, so a test ID can be copied from it."""
    summaries = list_test_runs()

    if not summaries:
        print("No archived runs yet. Run `python main.py` first.")
        return

    for summary in summaries:
        print(
            f"{summary.test_id}  {summary.ammeter_type:<10} "
            f"{summary.started_at:%Y-%m-%d %H:%M:%S} UTC  "
            f"{summary.sample_count} sample(s)  "
            f"mean {summary.mean_current:.6g} A"
        )


def show_run(test_id):
    """Print one archived run: metadata, statistics, and its raw samples."""
    result = load_test_run(test_id)

    print(f"Run {result.test_id}")
    print(f"  device     {result.ammeter_type}")
    print(f"  started    {result.started_at:%Y-%m-%d %H:%M:%S} UTC")
    print(f"  completed  {result.completed_at:%Y-%m-%d %H:%M:%S} UTC")
    config = result.sampling_config
    print(
        f"  sampling   {config.measurements_count} measurement(s) over "
        f"{config.total_duration_seconds:.6g} s at "
        f"{config.sampling_frequency_hz:.6g} Hz"
    )
    print()
    print(result.analysis)
    print()
    print("Samples")

    for index, measurement in enumerate(result.measurements, start=1):
        print(
            f"  {index:<4} {measurement.timestamp:%H:%M:%S.%f} "
            f"{measurement.current:.6g} {measurement.unit}"
        )


def start_emulators():
    """Start the three emulator threads and wait for them to bind."""
    # As supplied only Greenlee was started - the other two lines were commented
    # out, so a run reached the framework with two of the three devices missing
    # and reported them as connection failures (ISS-25).
    threading.Thread(target=run_greenlee_emulator, daemon=True).start()
    threading.Thread(target=run_entes_emulator, daemon=True).start()
    threading.Thread(target=run_circutor_emulator, daemon=True).start()

    # Wait for the servers to bind before the first measurement. The supplied
    # per-device client calls that used to live here are gone: the framework
    # reaches the same devices through the unified API, driven by the registry
    # in config.yaml.
    time.sleep(EMULATOR_STARTUP_SECONDS)


def run_ammeters():
    """Start the emulators and run a test against every configured device."""
    start_emulators()

    framework = AmmeterTestFramework()

    # Driven off the config registry, so adding a device stays a YAML edit.
    precision_results = []

    for ammeter_type in framework.config["ammeters"]:
        try:
            result = framework.run_test(ammeter_type)
            precision = framework.evaluate_precision(result.analysis)
            precision_results.append(precision)

            # The run's statistics, printed as well as archived and logged. Mean,
            # median, standard deviation, min and max are the five metrics the
            # assignment asks for, and without this line a plain `python main.py`
            # showed only the precision ranking underneath.
            print()
            print(result.analysis)

            # Archived first, then plotted into the same directory under the same
            # test ID, so a run's JSON and its PNG are found together.
            save_test_run(result)
            plot_path = plot_measurement_series(result)
            print(f"Saved {ammeter_type} measurement series plot: {plot_path}")

        # AmmeterError: the device could not be reached or replied unusably.
        # ValueError: it was reached but yielded nothing to analyse, because
        # every sample was skipped on a bad reply. Either way one bad device
        # must not cost the others their run.
        except (AmmeterError, ValueError) as exc:
            print(f"Skipping {ammeter_type}: {exc}")

    # Every device failed; there is nothing to rank and nothing to report.
    if not precision_results:
        print("\nNo device produced measurements, so there is nothing to compare.")
    else:
        print()
        print("PRECISION COMPARISON")
        print(framework.compare_precision(precision_results))

    # Otherwise the archive is only discoverable by reading the source.
    print("\nArchived under results/runs - see `python main.py --list`.")


def monitor(interval: float):
    """Sample every device on a fixed interval and export the results to Prometheus.

    Runs are not archived here: at one cycle every few seconds the JSON and PNG
    per run would grow without bound, and in this mode Prometheus is the store.
    """
    if interval <= 0:
        raise SystemExit("error: --interval must be greater than zero")

    # Imported here so a plain run works without prometheus-client installed.
    from src.observability import metrics

    start_emulators()

    framework = AmmeterTestFramework()
    ammeter_types = list(framework.config["ammeters"])

    metrics.start_metrics_server(ammeter_types=ammeter_types)
    print(
        f"Serving metrics on http://localhost:{metrics.DEFAULT_METRICS_PORT}/metrics, "
        f"sampling every {interval:g} s. Ctrl-C to stop."
    )

    start_time = time.monotonic()
    cycle = 0

    while True:
        for ammeter_type in ammeter_types:
            try:
                result = framework.run_test(ammeter_type)
                metrics.record_analysis(result.analysis)
                print(
                    f"{ammeter_type:<10} {result.analysis.sample_count} sample(s)  "
                    f"mean {result.analysis.mean_current:.6g} A"
                )

            # Same two failure modes as a single run: unreachable or unusable
            # device, and a device whose samples were all skipped. One bad
            # device must not end the monitoring loop.
            except (AmmeterError, ValueError) as exc:
                metrics.record_error(ammeter_type)
                print(f"Skipping {ammeter_type}: {exc}")

        # Target absolute ticks rather than sleeping `interval` after each cycle,
        # so the cycle's own duration does not push the schedule later and later.
        # A cycle that overruns its slot skips forward to the next future tick
        # instead of trying to catch up with back-to-back cycles.
        cycle += 1
        next_tick = start_time + (cycle * interval)
        now = time.monotonic()

        if next_tick <= now:
            cycle = math.ceil((now - start_time) / interval)
            next_tick = start_time + (cycle * interval)

        time.sleep(next_tick - now)


if __name__ == "__main__":
    args = parse_args()

    if args.monitor:
        # Ctrl-C is how this mode is meant to end, so it exits quietly rather
        # than with a KeyboardInterrupt traceback.
        try:
            monitor(args.interval)
        except KeyboardInterrupt:
            print("\nStopped.")

    elif not (args.list or args.show or args.compare):
        run_ammeters()
    else:
        # The archive options only read files, so they skip the emulator
        # threads and the startup wait entirely.
        #
        # FileNotFoundError: no run with that ID. ResultStoreError: the file
        # is there but unreadable. Both exit non-zero with one line, rather
        # than a traceback.
        try:
            if args.list:
                list_runs()
            elif args.show:
                show_run(args.show)
            else:
                print(compare_test_runs(args.compare))

        except (FileNotFoundError, ResultStoreError) as exc:
            raise SystemExit(f"error: {exc}")
