import logging

from Ammeters.base_ammeter import AmmeterEmulatorBase
from src.utils.Utils import generate_random_float

# See Greenlee_Ammeter: no handler here, the running program decides.
logger = logging.getLogger(__name__)


class CircutorAmmeter(AmmeterEmulatorBase):
    @property
    def get_current_command(self) -> bytes:
        # Define the command to get the current from CIRCUTOR
        return b'MEASURE_CIRCUTOR -get_measurement -current'

    def measure_current(self) -> float:
        num_samples = 10
        time_step = generate_random_float(0.001, 0.01)  # Time step (0.001s - 0.01s)
        voltages = [generate_random_float(0.1, 1.0) for _ in range(num_samples)]  # Voltage values

        current = sum(v * time_step for v in voltages)
        # One record instead of the supplied two: the pair straddled the summation, so
        # a concurrent device's line could land between a reading and its own current.
        logger.debug(
            "CIRCUTOR Ammeter - Voltages: %s, Time Step: %ss, Current: %sA",
            voltages, time_step, current,
        )
        return current
