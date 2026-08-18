
from typing import Dict

from Ammeters.client import request_current_from_ammeter
from src.testing.measurement import Measurement
from src.utils.config import load_config


class AmmeterTestFramework:
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config = load_config(config_path)
        
    def run_test(self, ammeter_type: str) -> Dict:
        pass


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
