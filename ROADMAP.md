# Roadmap

A living document. Check items off as they ship. Last updated: 2026-08-22.

Milestones 1–5 are the five sections of the assignment's Problem Statement, in its order and
under its names. Milestone 0 (fixing the supplied code) and Milestone 6 (documentation) are
not in the Problem Statement but are required by the assignment's Technical Requirements and
Deliverables. Individual bugs are tracked by ID in [`ISSUES.md`](ISSUES.md); fixes and design
decisions are recorded in [`IMPLEMENTATION_NOTES.md`](IMPLEMENTATION_NOTES.md).

**Observability** is not a phase of its own — each milestone carries one line of metrics work.
Runs are short-lived batch jobs, so a completed run pushes metrics to a Prometheus
**Pushgateway**; Prometheus scrapes it and Grafana reads from Prometheus, with the whole stack
coming up from a committed `docker-compose.yml`. It stays optional at runtime: the framework
must always produce results with the stack down.

**Status:** ⬜ not started · 🟡 in progress · ✅ done

An unticked box is work still intended. A box marked **⏸ deferred** is not: it depends on a
finding that the [triage in `ISSUES.md`](ISSUES.md#triage-2026-08-22) consciously took off the
work list, and the note says what leaving it costs. Deferred boxes are counted as settled when
judging whether a milestone is complete — otherwise every milestone stays 🟡 forever on work
nobody intends to do.

---

## 🟡 Milestone 0 — Supplied code fixed

*Goal: `python main.py` runs end to end and returns real data from all three ammeters.*

- [x] Repository audited and every bug catalogued (`ISSUES.md`)
- [x] Ports and commands reconciled across `main.py`, `config.yaml` and `README.md` — ISS-01, ISS-02, ISS-07
- [x] Client returns a parsed `float`, with a socket timeout and typed errors — ISS-04, ISS-12
- [x] `test_framework.py` imports cleanly; all four directories are packages — ISS-05, ISS-19 (partial)
- [x] `python main.py` prints a real reading from all three ammeters
- [ ] Emulators: `SO_REUSEADDR` and an explicit reply to unknown commands — ISS-10, ISS-11.
      The unknown-command reply shipped (ISS-11 ☑); `SO_REUSEADDR` (ISS-10) has not. Clean
      shutdown was part of this line and is now **⏸ deferred** with ISS-18
- [ ] ⏸ **Deferred** — config loading: UTF-8, validation, path resolved from the project root
      — ISS-15, ISS-19. The framework runs from the repo root only; the README says so
- [x] Logger actually writes to `results/logs/` — ISS-09; one file per run, DEBUG detail to
      the file and warnings to stderr, explicit UTF-8, path resolved from the project root
- [ ] `examples/run_tests.py` runs — ISS-06
- [x] Emulator print flood removed, including the `Ω` crash on non-UTF-8 consoles — ISS-22,
      ISS-24. The console text says `Ohm`, and the per-measurement `print()`s became
      `logger.debug` on the ISS-09 branch as planned. `base_ammeter`'s one-line startup
      message stays a `print`: it is once per process and the only signal the servers are up
- [ ] **Observability:** `docker-compose.yml`, scrape config and auto-provisioned Grafana datasource committed and verified up

## 🟡 Milestone 1 — Unified Measurement API

*Goal: one testing interface that works with multiple ammeter types and reports results
consistently.*

- [x] A single call measures Greenlee, ENTES and CIRCUTOR
- [x] All three return the same result type — `Measurement` (device, current, unit, UTC timestamp)
- [x] Failures surface as one error family regardless of device — `AmmeterError`
- [x] Device name, port and command come from `config.yaml`; a fourth ammeter is a config entry plus an emulator class
- [ ] ⏸ **Deferred** — emulator start/stop controllable from the framework, not only from
      `main.py`; needs the lifecycle work in ISS-18
- [ ] **Observability:** one shared registry behind the client, so every device is instrumented identically — call counter, error counter by failure kind, and latency histogram, all labelled by ammeter type

## 🟡 Milestone 2 — Measurement Sampling

*Goal: configurable sampling with precise timing and data collection.*

- [x] A run is driven by number of measurements, by total duration, or by sampling frequency
- [x] Rule for combining the three defined and documented — they are over-determined, so any
      two derive the third and a contradictory trio is rejected, in place of a precedence rule
- [x] Configured values validated before use: positive numbers only, a derived count floored
      and its duration recomputed, so the resolved config always describes the actual run
- [x] Monotonic, drift-free timing — each sample targets `start + index × period`
- [ ] Achieved rate reported next to the requested rate; overrun is currently silent
- [ ] A failed sample is tallied and the run continues rather than aborting — a bad reply is
      skipped but not counted, and an unreachable device still aborts the run by design
- [x] Sampling parameters read from `config.yaml` with real defaults, no `NULL` placeholders — ISS-13
- [ ] **Observability:** requested vs achieved rate, per-run success/failure counts, run duration and timing drift pushed at the end of each run

## 🟡 Milestone 3 — Result Analysis

*Goal: comprehensive statistics over a run.*

- [x] Mean, median, standard deviation, minimum and maximum current per run
- [ ] Sample count and failure count reported alongside the statistics — sample count is in
      `AnalysisResult`; the failure tally is the open Milestone 2 item above
- [x] Computed with the standard library `statistics` module unless an added dependency is justified
- [x] Statistics over a mixed-device list rejected, and the device recorded on the result —
      the three emulators read in different magnitudes, so a statistic spanning them is
      meaningless — ISS-23
- [x] Run summary printed in a clear, readable format — `AnalysisResult.__str__`; six
      significant figures, since the devices read orders of magnitude apart. Milestone 5
      replaced the per-device sweep in `main.py` with the comparison table, so median, min
      and max are archived but no longer printed to the console
- [ ] *(Bonus)* Measurement series over time and per-device distribution plots saved with the run
- [x] *(Bonus)* Performance consistency evaluated with a named variability metric —
      coefficient of variation, delivered with Milestone 5
- [ ] **Observability:** the five statistics pushed as labelled gauges, with a provisioned Grafana dashboard panel for each

## 🟡 Milestone 4 — Result Management

*Goal: a robust archive of every test run.*

- [x] Unique run ID for every run — UUID4, assigned in `run_test`
- [x] Metadata stored: timestamp, ammeter type, sampling configuration
- [x] Raw samples persisted, not only the computed summary
- [x] Past runs can be listed, retrieved by ID, and compared side by side — listing returns
      `RunSummary` ordered by start time; comparison renders archived statistics as a table
      and computes nothing across runs
- [x] Portable, human-readable storage under `results/` (JSON and/or CSV) — one JSON file per
      run, path resolved from the project root; JSON only, no CSV export
- [ ] **Observability:** run ID travels as a label, grouping keys chosen so a new run cannot overwrite the previous one, label cardinality documented

## 🟡 Milestone 5 — Accuracy Assessment *(bonus)*

*Goal: compare measurements across ammeter types and quantify precision.*

- [x] Runs from different device types compared in a single report — `compare_precision`
      renders every device as one ranked table, printed by `main.py`
- [x] The differing magnitudes across devices handled explicitly — normalised, or an agreed
      reference stated — ISS-23; normalised by dividing the standard deviation by the mean,
      and the report states that no reference current exists
- [ ] Relative accuracy quantified per device — **not delivered, by design.** The emulators
      expose no shared reference current, so any accuracy figure would measure against an
      invented truth. Precision is reported instead and the report says which it is
- [x] Precision quantified using a named statistical technique — coefficient of variation
      (`stdev / |mean|`), standard library only
- [ ] Most reliable measurement method identified, with the reasoning recorded — devices are
      ranked, but no winner is declared: at the default 5 samples the gaps are smaller than
      the sampling noise, and a separability test was cut as over-engineering
- [ ] **Observability:** cross-device dashboard on shared normalised axes, with a side-by-side precision panel

## ⬜ Milestone 6 — Documentation & polish

*Goal: the assignment's deliverables, complete and accurate.*

- [ ] `README.md` structure, ports and commands match the real repo; install and usage instructions present — ISS-14
- [ ] `requirements.txt` lists only what is actually imported — ISS-21. The five unused
      scientific packages are still listed; `pytest` and `pytest-cov` were added on top and
      are the exception this line does not cover — they are test-only by design and marked
      as such in the file
- [ ] Sample test results committed (raw samples, statistics, metadata, plots) — one curated
      run per device is committed under `results/samples/` with raw samples, statistics and
      metadata; the plots are still missing, pending the section 3 visualisation bonus
- [ ] `IMPLEMENTATION_NOTES.md` complete: every fix, every design decision and rejected alternative, every added dependency
- [ ] Verified on Windows and on at least one POSIX system — CI runs the suite on Linux;
      manual end-to-end verification on a POSIX system is still outstanding
- [x] Automated tests in CI as a blocking gate — `pytest` over `tests/`, 98% coverage of
      `src/` against an 85% floor (`--cov-fail-under=85`). Not an assignment deliverable;
      recorded here because it gates every milestone above it
- [ ] **Observability:** stack documented in the README, dashboard JSON committed, and the framework verified to produce complete results with the stack shut down
