import threading
import time

from src.testing.test_framework import AmmeterTestFramework
from src.testing.result_manager import save_test_run
from src.testing.visualization import plot_measurement_series

from Ammeters.Circutor_Ammeter import CircutorAmmeter
from Ammeters.Entes_Ammeter import EntesAmmeter
from Ammeters.Greenlee_Ammeter import GreenleeAmmeter
from Ammeters.client import request_current_from_ammeter, AmmeterError


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
    # Start each ammeter in a separate thread
    threading.Thread(target=run_greenlee_emulator, daemon=True).start()
    # threading.Thread(target=run_entes_emulator, daemon=True).start()
    # threading.Thread(target=run_circutor_emulator, daemon=True).start()

    # This section is commented out because it shouldn't work.
    # Read the README.md file as well as the source code if you need, and fix the problem.

    # Wait for the servers to start, if you have problem restarting the servers between runs try increasing sleep time.
    time.sleep(5)
    # request_current_from_ammeter(5001, b'MEASURE_GREENLEE -get_measurement')  # Request from Greenlee Ammeter
    # request_current_from_ammeter(5002, b'MEASURE_ENTES -get_data')  # Request from ENTES Ammeter
    # request_current_from_ammeter(5003, b'MEASURE_CIRCUTOR -get_measurement -current')  # Request from CIRCUTOR Ammeter

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
