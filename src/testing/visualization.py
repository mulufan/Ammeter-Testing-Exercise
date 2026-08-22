"""
One plot per run: measured current against the time each sample was taken.

Deliberately the smallest thing that answers "what did this run look like" -
a single line chart per `TestRunResult`, written next to that run's JSON
archive under the same test ID. Distribution plots, comparison charts and
anything interactive are out of scope here; `analysis.visualization.plot_types`
in `config.yaml` is still unread.
"""

from pathlib import Path

import matplotlib

# Selected before pyplot is imported, which is the only point at which it takes
# effect. These figures are only ever written to a file, and the default
# interactive backend needs a display - without this, importing the module fails
# outright on CI and on any headless machine.
matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402  - must follow the backend choice

from src.testing.models import TestRunResult
from src.testing.result_manager import RESULTS_DIR


def plot_measurement_series(
    result: TestRunResult, output_dir: Path = RESULTS_DIR
) -> Path:
    """
    Render one run's samples as a line plot and save it as a PNG.

    The file is `<test_id>.png` in the archive directory, so a run's plot sits
    beside its `<test_id>.json` and both are found by the same ID. Returns the
    path written.

    Raises ValueError for a run with no samples: `collect_samples` can
    legitimately return `[]` when every read fails, and an empty pair of axes
    would archive as though the run had something to show.
    """
    if not result.measurements:
        raise ValueError(
            f"Run {result.test_id} has no measurements to plot."
        )

    timestamps = [measurement.timestamp for measurement in result.measurements]
    currents = [measurement.current for measurement in result.measurements]

    figure, axes = plt.subplots()

    # Markers as well as the line: at the default five samples a bare line hides
    # where the readings actually are.
    axes.plot(timestamps, currents, marker="o")
    # The short ID matches the run's log filename and the comparison table; the
    # full ID is the filename of the plot itself.
    axes.set_title(f"{result.ammeter_type} - run {result.test_id[:8]}")
    axes.set_xlabel("Measurement time (UTC)")
    axes.set_ylabel("Current (A)")
    axes.grid(True)
    # Timestamps are long enough to collide on the x-axis at any sample count.
    figure.autofmt_xdate()

    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / f"{result.test_id}.png"
    figure.savefig(file_path)

    # pyplot keeps every figure it creates alive until it is closed; a run that
    # plots three devices would otherwise leak three figures per process.
    plt.close(figure)

    return file_path
