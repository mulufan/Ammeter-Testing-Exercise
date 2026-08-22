import logging

from Ammeters.base_ammeter import AmmeterEmulatorBase
from src.utils.Utils import generate_random_float

# No handler is attached here: an emulator is a library, and choosing where its
# output goes belongs to whatever is running it. A driver that wants these lines
# calls logging.basicConfig(level=logging.DEBUG); otherwise they cost nothing.
logger = logging.getLogger(__name__)


class GreenleeAmmeter(AmmeterEmulatorBase):
    @property
    def get_current_command(self) -> bytes:
        # Define the command to get the current from Greenlee
        return b'MEASURE_GREENLEE -get_measurement'

    def measure_current(self) -> float:
        voltage = generate_random_float(1.0, 10.0)  # Random voltage (1V - 10V)
        resistance = generate_random_float(0.1, 100.0)  # Random resistance (0.1 Ohm - 100 Ohm)
        current = voltage / resistance
        # "Ohm", not the U+03A9 sign (ISS-24): a non-UTF-8 console raises
        # UnicodeEncodeError inside the handler, and this text may still reach one.
        logger.debug(
            "Greenlee Ammeter - Voltage: %sV, Resistance: %s Ohm, Current: %sA",
            voltage, resistance, current,
        )
        return current
