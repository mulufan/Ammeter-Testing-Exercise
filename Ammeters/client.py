from socket import socket, AF_INET, SOCK_STREAM

DEFAULT_TIMEOUT_SECONDS = 5.0  # Default timeout for socket operations in seconds

class AmmeterError(RuntimeError):
    """Base exception for ammeter communication failures."""


class AmmeterConnectionError(AmmeterError):
    """Raised when communication with an ammeter fails."""


class AmmeterResponseError(AmmeterError):
    """Raised when an ammeter returns an invalid response."""


def request_current_from_ammeter(
    port: int,
    command: bytes,
    timeout: float = DEFAULT_TIMEOUT_SECONDS
) -> float:
    """
    Send a measurement command to an ammeter and return the current in amperes.
    Raises a clear error if communication fails or the response is invalid.
    """
    try:
        with socket(AF_INET, SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect(("localhost", port))
            s.sendall(command)
            data = s.recv(1024)

        if data:
            try:
                # NOTE (MF): commented out print and returning the measurement
                # print(f"Received current measurement from port {port}: {data.decode('utf-8')} A")
                return float(data.decode("utf-8"))
            except (UnicodeDecodeError, ValueError) as exc:
                raise AmmeterResponseError(
                    f"Invalid response received from ammeter on port {port}"
                ) from exc
        else:
            raise AmmeterResponseError(f"No response received from ammeter on port {port}")

    except OSError as exc:
        raise AmmeterConnectionError(
            f"Failed to read current from ammeter on port {port}: {exc}"   
        ) from exc
