"""Prometheus metrics for monitor mode.

The only module that imports `prometheus_client`, so the package stays an
optional dependency: a plain `python main.py` never reaches this file.
"""

from prometheus_client import CollectorRegistry, Counter, Gauge, start_http_server

DEFAULT_METRICS_PORT = 8000

# A private registry rather than the default one: nothing else in this project
# exports metrics, and it keeps the endpoint to our six series plus the client's
# own process metrics being absent.
REGISTRY = CollectorRegistry()

LABELS = ("ammeter",)

MEAN_CURRENT = Gauge(
    "ammeter_current_amperes",
    "Mean current of the most recent test run, in amperes.",
    LABELS,
    registry=REGISTRY,
)
STDDEV_CURRENT = Gauge(
    "ammeter_current_stddev_amperes",
    "Sample standard deviation of the most recent test run, in amperes.",
    LABELS,
    registry=REGISTRY,
)
MIN_CURRENT = Gauge(
    "ammeter_current_min_amperes",
    "Lowest reading of the most recent test run, in amperes.",
    LABELS,
    registry=REGISTRY,
)
MAX_CURRENT = Gauge(
    "ammeter_current_max_amperes",
    "Highest reading of the most recent test run, in amperes.",
    LABELS,
    registry=REGISTRY,
)
SAMPLE_COUNT = Gauge(
    "ammeter_sample_count",
    "Samples collected in the most recent test run.",
    LABELS,
    registry=REGISTRY,
)
ERRORS = Counter(
    "ammeter_errors_total",
    "Test cycles that failed for this ammeter.",
    LABELS,
    registry=REGISTRY,
)


def start_metrics_server(port: int = DEFAULT_METRICS_PORT, ammeter_types=()) -> None:
    """Serve /metrics on a background thread.

    Touching each error counter up front publishes the series at zero, so a
    dashboard panel has something to plot before the first failure.
    """
    for ammeter_type in ammeter_types:
        ERRORS.labels(ammeter=ammeter_type)

    start_http_server(port, registry=REGISTRY)


def record_analysis(analysis) -> None:
    """Publish one run's statistics as the current value of each gauge."""
    labels = {"ammeter": analysis.ammeter_type}

    MEAN_CURRENT.labels(**labels).set(analysis.mean_current)
    MIN_CURRENT.labels(**labels).set(analysis.min_current)
    MAX_CURRENT.labels(**labels).set(analysis.max_current)
    SAMPLE_COUNT.labels(**labels).set(analysis.sample_count)

    # Undefined at a single sample; left at its previous value rather than
    # published as 0, which would read as perfect precision.
    if analysis.standard_deviation is not None:
        STDDEV_CURRENT.labels(**labels).set(analysis.standard_deviation)


def record_error(ammeter_type: str) -> None:
    """Count one failed cycle, so a silent device is visible as a rising rate."""
    ERRORS.labels(ammeter=ammeter_type).inc()
