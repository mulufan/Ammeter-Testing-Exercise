from Ammeters.base_ammeter import AmmeterEmulatorBase
from src.utils.Utils import generate_random_float


class GreenleeAmmeter(AmmeterEmulatorBase):
    @property
    def get_current_command(self) -> bytes:
        # Define the command to get the current from Greenlee
        return b'MEASURE_GREENLEE -get_measurement'

    def measure_current(self) -> float:
        voltage = generate_random_float(1.0, 10.0)  # Random voltage (1V - 10V)
        resistance = generate_random_float(0.1, 100.0)  # Random resistance (0.1 Ohm - 100 Ohm)
        current = voltage / resistance
        # "Ohm", not the U+03A9 sign: this line is written to whatever console the
        # operator happens to have, and a non-UTF-8 code page (cp1255, cp1252, ...)
        # raises UnicodeEncodeError here, out of the accept loop, killing the thread.
        print(f"Greenlee Ammeter - Voltage: {voltage}V, Resistance: {resistance} Ohm, Current: {current}A")
        return current
