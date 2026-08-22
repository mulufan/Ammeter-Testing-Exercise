"""
The run archive: save, load it back unchanged, list, compare, and fail loudly
when a stored run cannot be read.

Every test archives into `tmp_path`, so the suite never touches `results/runs/`.
"""

import json
from datetime import datetime, timezone

import pytest

from src.testing.result_manager import (
    ResultStoreError,
    compare_test_runs,
    list_test_runs,
    load_test_run,
    save_test_run,
)
from tests.conftest import make_test_run


def test_a_saved_run_loads_back_unchanged(tmp_path):
    original = make_test_run(currents=(1.0, 2.0, 3.0))

    save_test_run(original, tmp_path)
    loaded = load_test_run(original.test_id, tmp_path)

    # Whole-object equality: the dataclasses are frozen and compare by value, so
    # this covers the sampling config, every raw sample and every statistic at
    # once - including the timestamps, which are the part that survives a JSON
    # round trip only because they are written and parsed as ISO strings.
    assert loaded == original


def test_saving_names_the_file_after_the_run_id(tmp_path):
    result = make_test_run()

    file_path = save_test_run(result, tmp_path)

    assert file_path == tmp_path / f"{result.test_id}.json"
    assert file_path.exists()


def test_loading_an_unknown_run_says_so(tmp_path):
    # Distinct from a damaged archive: nothing was ever stored under this ID.
    with pytest.raises(FileNotFoundError):
        load_test_run("no-such-run", tmp_path)


def test_a_truncated_archive_is_reported_not_silently_skipped(tmp_path):
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(ResultStoreError, match="not valid JSON"):
        load_test_run("broken", tmp_path)


def test_an_archive_missing_a_field_is_reported(tmp_path):
    result = make_test_run()
    save_test_run(result, tmp_path)

    file_path = tmp_path / f"{result.test_id}.json"
    data = json.loads(file_path.read_text(encoding="utf-8"))
    del data["analysis"]["mean_current"]
    file_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ResultStoreError, match="not a readable test run"):
        load_test_run(result.test_id, tmp_path)


def test_listing_an_empty_archive_returns_nothing(tmp_path):
    assert list_test_runs(tmp_path / "never-created") == []


def test_listing_summarises_runs_oldest_first(tmp_path):
    older = make_test_run(
        test_id="aaaaaaaa-0000-0000-0000-000000000000",
        started_at=datetime(2026, 8, 22, 9, 0, tzinfo=timezone.utc),
    )
    newer = make_test_run(
        test_id="00000000-0000-0000-0000-00000000bbbb",
        started_at=datetime(2026, 8, 22, 10, 0, tzinfo=timezone.utc),
    )

    save_test_run(older, tmp_path)
    save_test_run(newer, tmp_path)

    summaries = list_test_runs(tmp_path)

    # Ordered by start time, not by filename: a UUID sorts arbitrarily, and the
    # IDs here are chosen so the two orderings disagree.
    assert [summary.test_id for summary in summaries] == [older.test_id, newer.test_id]
    assert summaries[0].mean_current == older.analysis.mean_current
    assert summaries[0].sample_count == 3


def test_comparing_runs_from_different_devices_warns_about_magnitudes(tmp_path):
    greenlee = make_test_run(
        test_id="aaaaaaaa-0000-0000-0000-000000000000", ammeter_type="greenlee"
    )
    entes = make_test_run(
        test_id="bbbbbbbb-0000-0000-0000-000000000000",
        ammeter_type="entes",
        currents=(100.0, 110.0, 120.0),
    )
    save_test_run(greenlee, tmp_path)
    save_test_run(entes, tmp_path)

    report = compare_test_runs([greenlee.test_id, entes.test_id], tmp_path)

    assert "greenlee" in report and "entes" in report
    assert "not an accuracy comparison" in report
    # Short IDs identify the rows, so the full ones are listed for copying back.
    assert greenlee.test_id in report


def test_comparing_nothing_is_an_error(tmp_path):
    with pytest.raises(ValueError, match="no test IDs"):
        compare_test_runs([], tmp_path)
