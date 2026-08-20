import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from src.testing.models import (
    AnalysisResult,
    Measurement,
    RunSummary,
    SamplingConfig,
    TestRunResult,
)

# Resolved from this file rather than the working directory. `results/runs` is a
# fixed location in the project, and a CWD-relative path made `list_test_runs()`
# return [] from anywhere else - indistinguishable from an empty archive - while
# `save_test_run()` quietly started a second archive tree next to the caller.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = PROJECT_ROOT / "results" / "runs"

# Six significant figures, matching AnalysisResult.__str__: the devices read
# three orders of magnitude apart, so a fixed decimal count renders every
# CIRCUTOR statistic as 0.01.
CURRENT_FORMAT = ".6g"


class ResultStoreError(RuntimeError):
    """
    Raised when an archived run exists but cannot be read back.

    One type on purpose. A caller facing a damaged archive takes the same action
    whether the JSON was truncated, a field went missing or a timestamp failed to
    parse, so splitting those apart would only add names. A run that was never
    archived stays `FileNotFoundError`, which already says exactly that.
    """


def _make_json_serializable(value):
    """
    Convert datetime values inside a test result to ISO strings
    so the result can be stored as JSON.
    """
    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, dict):
        return {
            key: _make_json_serializable(item) for key, item in value.items()
        }

    if isinstance(value, list):
        return [_make_json_serializable(item) for item in value]

    return value


def save_test_run(result: TestRunResult, results_dir: Path = RESULTS_DIR) -> Path:
    """
    Archive a completed test run as a JSON file named after its unique test ID.

    The whole run is stored - sampling configuration, every raw sample and the
    statistics - so an archived run can be re-read without the process that
    produced it. Returns the path written.
    """
    results_dir.mkdir(parents=True, exist_ok=True)

    file_path = results_dir / f"{result.test_id}.json"
    # from dataclasses to dict
    result_data = asdict(result)
    # from dict to json serializable (datetime to str)
    result_data = _make_json_serializable(result_data)

    with file_path.open("w", encoding="utf-8") as file:
        json.dump(result_data, file, indent=2)

    return file_path


def _build_test_run(data: dict, file_path: Path) -> TestRunResult:
    """
    Rebuild the dataclasses from parsed JSON.

    Fields are named explicitly rather than splatted with `**`, so a field added
    by a later version is ignored instead of raising `TypeError` on every older
    reader. Anything genuinely wrong - a missing field, a timestamp that will not
    parse - is reported as one ResultStoreError naming the file.
    """
    try:
        sampling_config = SamplingConfig(
            measurements_count=data["sampling_config"]["measurements_count"],
            total_duration_seconds=data["sampling_config"]["total_duration_seconds"],
            sampling_frequency_hz=data["sampling_config"]["sampling_frequency_hz"],
        )

        measurements = [
            Measurement(
                ammeter_type=item["ammeter_type"],
                current=item["current"],
                unit=item["unit"],
                timestamp=datetime.fromisoformat(item["timestamp"]),
            )
            for item in data["measurements"]
        ]

        analysis = AnalysisResult(
            ammeter_type=data["analysis"]["ammeter_type"],
            sample_count=data["analysis"]["sample_count"],
            mean_current=data["analysis"]["mean_current"],
            median_current=data["analysis"]["median_current"],
            standard_deviation=data["analysis"]["standard_deviation"],
            min_current=data["analysis"]["min_current"],
            max_current=data["analysis"]["max_current"],
        )

        return TestRunResult(
            test_id=data["test_id"],
            ammeter_type=data["ammeter_type"],
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=datetime.fromisoformat(data["completed_at"]),
            sampling_config=sampling_config,
            measurements=measurements,
            analysis=analysis,
        )

    # KeyError: a field is absent. TypeError: a field holds the wrong type, e.g.
    # a null timestamp. ValueError: a field is the right type but unparseable.
    except (KeyError, TypeError, ValueError) as exc:
        raise ResultStoreError(
            f"{file_path} is not a readable test run: {exc!r}"
        ) from exc


def load_test_run(test_id: str, results_dir: Path = RESULTS_DIR) -> TestRunResult:
    """
    Load an archived test run by its unique test ID.

    Raises FileNotFoundError when there is no such run, and ResultStoreError when
    the file exists but its contents cannot be read back.
    """
    file_path = results_dir / f"{test_id}.json"

    if not file_path.exists():
        raise FileNotFoundError(f"Test run not found: {test_id}")

    with file_path.open("r", encoding="utf-8") as file:
        try:
            data = json.load(file)
        except json.JSONDecodeError as exc:
            raise ResultStoreError(
                f"{file_path} is not valid JSON: {exc}"
            ) from exc

    return _build_test_run(data, file_path)


def list_test_runs(results_dir: Path = RESULTS_DIR) -> list[RunSummary]:
    """
    Summarise every archived run, oldest first.

    Ordered by start time rather than by ID: a UUID sorts arbitrarily, so a list
    of sorted filenames said nothing about when a run happened, and choosing a
    run to retrieve meant opening every file.

    A file that cannot be read raises rather than being skipped. Discovery that
    quietly drops damaged runs is how an archive rots without anyone noticing.
    """
    if not results_dir.exists():
        return []

    summaries = [
        RunSummary.from_test_run(load_test_run(file_path.stem, results_dir))
        for file_path in results_dir.glob("*.json")
    ]

    return sorted(summaries, key=lambda summary: summary.started_at)


def _format_current(value: float | None) -> str:
    """Render one statistic, keeping an undefined standard deviation non-numeric."""
    return "n/a" if value is None else format(value, CURRENT_FORMAT)


def compare_test_runs(
    test_ids: list[str], results_dir: Path = RESULTS_DIR
) -> str:
    """
    Render archived runs side by side as a text table.

    Presentation only: every number shown was computed when its run was
    archived, and nothing is calculated across runs. Judging *accuracy* between
    device types needs the magnitude mismatch in ISS-23 resolved first and
    belongs to section 5; a selection spanning several devices is tabulated with
    a warning rather than combined into a single figure.
    """
    if not test_ids:
        raise ValueError("Nothing to compare: no test IDs given.")

    summaries = [
        RunSummary.from_test_run(load_test_run(test_id, results_dir))
        for test_id in test_ids
    ]

    columns = (
        ("run", 10),
        ("device", 10),
        ("started (UTC)", 21),
        ("n", 4),
        ("mean A", 13),
        ("stdev A", 13),
        ("min A", 13),
        ("max A", 13),
    )

    lines = ["  ".join(title.ljust(width) for title, width in columns).rstrip()]
    lines.append("-" * len(lines[0]))

    for summary in summaries:
        cells = (
            # The first block of a UUID is enough to identify a run in a table;
            # the full ID is listed underneath for copying back into load.
            summary.test_id.split("-")[0],
            summary.ammeter_type,
            summary.started_at.strftime("%Y-%m-%d %H:%M:%S"),
            str(summary.sample_count),
            _format_current(summary.mean_current),
            _format_current(summary.standard_deviation),
            _format_current(summary.min_current),
            _format_current(summary.max_current),
        )

        lines.append(
            "  ".join(
                cell.ljust(width) for cell, (_, width) in zip(cells, columns)
            ).rstrip()
        )

    devices = {summary.ammeter_type for summary in summaries}

    if len(devices) > 1:
        lines.append("")
        lines.append(
            f"Note: {len(devices)} device types compared ({', '.join(sorted(devices))}). "
            "They do not measure a shared current and read in different "
            "magnitudes, so these columns are not an accuracy comparison."
        )

    lines.append("")
    lines.append("Full run IDs:")
    lines.extend(f"  {summary.test_id}" for summary in summaries)

    return "\n".join(lines)
