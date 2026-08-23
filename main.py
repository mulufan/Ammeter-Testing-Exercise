import argparse
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


def run_ammeters():
    """Start the emulators and run a test against every configured device."""
    # Start each ammeter in a separate thread. As supplied only Greenlee was
    # started - the other two lines were commented out, so a run reached the
    # framework with two of the three devices missing and reported them as
    # connection failures (ISS-25).
    threading.Thread(target=run_greenlee_emulator, daemon=True).start()
    threading.Thread(target=run_entes_emulator, daemon=True).start()
    threading.Thread(target=run_circutor_emulator, daemon=True).start()

    # Wait for the servers to bind before the first measurement. The supplied
    # per-device client calls that used to live here are gone: the framework
    # below reaches the same devices through the unified API, driven by the
    # registry in config.yaml.
    time.sleep(5)

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


if __name__ == "__main__":
    args = parse_args()

    if not (args.list or args.show or args.compare):
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
