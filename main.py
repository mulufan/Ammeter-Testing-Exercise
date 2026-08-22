import threading
import time

from src.testing.test_framework import AmmeterTestFramework
from src.testing.result_manager import save_test_run
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

if __name__ == "__main__":
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
