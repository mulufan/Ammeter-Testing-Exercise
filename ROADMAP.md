# Roadmap

What shipped, and what was consciously left out. Last updated: 2026-08-23.

Milestones 1–5 are the five sections of the assignment's Problem Statement, in its order and
under its names. Milestone 0 (fixing the supplied code) and Milestone 6 (documentation) are
not in the Problem Statement but are required by the assignment's Technical Requirements and
Deliverables. Individual bugs are tracked by ID in [`ISSUES.md`](ISSUES.md); fixes and design
decisions are recorded in [`IMPLEMENTATION_NOTES.md`](IMPLEMENTATION_NOTES.md).

**Status:** ✅ done · 🟡 in progress · ⬜ not started

A milestone is ✅ when its stated goal is satisfied. Items marked **⏸ deferred** are not
oversights: each one was considered, taken off the work list, and left with a note saying
what leaving it costs. They stay listed under the milestone they belong to so the cost stays
visible, and they do not hold the milestone open. Work that was scoped beyond the assignment
and never started is collected under [Future Improvements](#future-improvements) rather than
sitting unticked inside a milestone.

---

## ✅ Milestone 0 — Supplied code fixed

*Goal: `python main.py` runs end to end and returns real data from all three ammeters.*

- [x] Repository audited and every bug catalogued (`ISSUES.md`)
- [x] Ports and commands reconciled across `main.py`, `config.yaml` and `README.md` — ISS-01, ISS-02, ISS-07
- [x] Client returns a parsed `float`, with a socket timeout and typed errors — ISS-04, ISS-12
- [x] `test_framework.py` imports cleanly; all four directories are packages — ISS-05, ISS-19 (partial)
- [x] `python main.py` prints a real reading from all three ammeters — all three emulator
      threads now start; two were still commented out from the supplied file and the run
      reached Greenlee only, found while verifying the README — ISS-25
- [x] Emulators answer an unknown command instead of dropping it silently — ISS-11
- [x] Logger actually writes to `results/logs/` — ISS-09; one file per run, DEBUG detail to
      the file and warnings to stderr, explicit UTF-8, path resolved from the project root
- [x] Emulator print flood removed, including the `Ω` crash on non-UTF-8 consoles — ISS-22,
      ISS-24. The console text says `Ohm`, and the per-measurement `print()`s became
      `logger.debug` on the ISS-09 branch as planned. `base_ammeter`'s one-line startup
      message stays a `print`: it is once per process and the only signal the servers are up
- [ ] ⏸ **Deferred** — `SO_REUSEADDR` on the emulator sockets (ISS-10). A restart inside the
      TCP `TIME_WAIT` window can still fail to bind; the workaround is to wait a few seconds,
      which is what the supplied comment already told the reader to do
- [ ] ⏸ **Deferred** — config schema validation and a project-root-relative config path
      (ISS-15, ISS-19). The UTF-8 encoding half was un-deferred and fixed on its own, being a
      stated Technical Constraint and one argument to `open`. The rest stays deferred, so the
      framework runs from the repository root only and the README says so
- [ ] ⏸ **Deferred** — `examples/run_tests.py` (ISS-06). Left as supplied: it still fails on
      import and calls `run_test()` with no argument. `main.py` and the framework API in the
      README are the supported entry points, and the README's *Known gaps* section says so
      rather than leaving a reader to discover it by running the file

## ✅ Milestone 1 — Unified Measurement API

*Goal: one testing interface that works with multiple ammeter types and reports results
consistently.*

- [x] A single call measures Greenlee, ENTES and CIRCUTOR
- [x] All three return the same result type — `Measurement` (device, current, unit, UTC timestamp)
- [x] Failures surface as one error family regardless of device — `AmmeterError`
- [x] Device name, port and command come from `config.yaml`; a fourth ammeter is a config entry plus an emulator class
- [ ] ⏸ **Deferred** — emulator start/stop controllable from the framework, not only from
      `main.py`; needs the lifecycle work in ISS-18. The emulators stand in for hardware the
      framework would not be starting in the first place, so the API is complete without it

## ✅ Milestone 2 — Measurement Sampling

*Goal: configurable sampling with precise timing and data collection.*

- [x] A run is driven by number of measurements, by total duration, or by sampling frequency
- [x] Rule for combining the three defined and documented — they are over-determined, so any
      two derive the third and a contradictory trio is rejected, in place of a precedence rule
- [x] Configured values validated before use: positive numbers only, a derived count floored
      and its duration recomputed, so the resolved config always describes the actual run
- [x] Monotonic, drift-free timing — each sample targets `start + index × period`
- [x] Sampling parameters read from `config.yaml` with real defaults, no `NULL` placeholders — ISS-13
- [ ] ⏸ **Deferred** — achieved sampling rate reported next to the requested rate. Timing is
      drift-free by construction, but an overrun on a slow device is currently silent rather
      than surfaced in the run summary
- [ ] ⏸ **Deferred** — per-run failure tally. A malformed reply is skipped and the run
      continues, but skipped samples are not counted, so a run that quietly lost samples reads
      the same as a clean one. An unreachable device aborts that device's run by design, and
      `main.py` still tests the others

## ✅ Milestone 3 — Result Analysis

*Goal: comprehensive statistics over a run.*

- [x] Mean, median, standard deviation, minimum and maximum current per run
- [x] Computed with the standard library `statistics` module unless an added dependency is justified
- [x] Statistics over a mixed-device list rejected, and the device recorded on the result —
      the three emulators read in different magnitudes, so a statistic spanning them is
      meaningless — ISS-23
- [x] Sample count reported alongside the statistics — `AnalysisResult.sample_count`
- [x] Run summary printed in a clear, readable format — `AnalysisResult.__str__`; six
      significant figures, since the devices read orders of magnitude apart. Milestone 5
      replaced the per-device sweep in `main.py` with the comparison table, which dropped
      median, min and max from the console; `main.py` prints the block per device again,
      above the table, so all five statistics are visible in a plain run
- [x] *(Bonus)* Measurement series plotted and saved with the run —
      `src/testing/visualization.py` writes one Matplotlib line plot per run to
      `results/runs/<test_id>.png`, beside the run's JSON
- [x] *(Bonus)* Performance consistency evaluated with a named variability metric —
      coefficient of variation, delivered with Milestone 5
- [ ] ⏸ **Deferred** — *(Bonus)* per-device distribution plots. The measurement-series plot
      covers the visualization deliverable; a histogram over the default five samples would
      show shape that is not there to see
- [ ] ⏸ **Deferred** — failure count beside the statistics, tied to the sampling tally above

## ✅ Milestone 4 — Result Management

*Goal: a robust archive of every test run.*

- [x] Unique run ID for every run — UUID4, assigned in `run_test`
- [x] Metadata stored: timestamp, ammeter type, sampling configuration
- [x] Raw samples persisted, not only the computed summary
- [x] Past runs can be listed, retrieved by ID, and compared side by side — listing returns
      `RunSummary` ordered by start time; comparison renders archived statistics as a table
      and computes nothing across runs
- [x] Portable, human-readable storage under `results/` (JSON and/or CSV) — one JSON file per
      run, path resolved from the project root; JSON only, no CSV export

## ✅ Milestone 5 — Accuracy Assessment *(bonus)*

*Goal: compare measurements across ammeter types and quantify precision.*

**What this milestone delivers is precision, not accuracy.** The devices are compared and
their relative variability is quantified with the coefficient of variation. True accuracy is
**not** implemented, and cannot be as the emulators stand: they expose no shared reference
current, so there is no ground truth to measure against. Quantifying real accuracy would
require all three devices to read a common reference current — see
[Future Improvements](#future-improvements).

- [x] Runs from different device types compared in a single report — `compare_precision`
      renders every device as one ranked table, printed by `main.py`
- [x] The differing magnitudes across devices handled explicitly — normalised, or an agreed
      reference stated — ISS-23; normalised by dividing the standard deviation by the mean,
      and the report states that no reference current exists
- [x] Precision quantified using a named statistical technique — coefficient of variation
      (`stdev / |mean|`), standard library only
- [x] The precision-is-not-accuracy limitation stated in the output itself, not only in the
      documentation — the caveats print directly beneath the comparison table
- [ ] ⏸ **Deferred, by design** — relative accuracy quantified per device. There is no shared
      reference current, so any accuracy figure would be measured against an invented truth.
      Reporting one would be worse than reporting none
- [ ] ⏸ **Deferred** — a single "most reliable" device declared. The devices are ranked, but
      no winner is named: at the default five samples the gaps are smaller than the sampling
      noise, and a separability test was cut as over-engineering for this exercise

## ✅ Milestone 6 — Documentation & polish

*Goal: the assignment's deliverables, complete and accurate.*

- [x] `README.md` structure, ports and commands match the real repo; install and usage
      instructions present — ISS-14. Rewritten around the finished solution: quick start,
      Mermaid architecture diagram, device and component tables, the sampling rule, where
      results are written, design decisions in brief, and the precision-is-not-accuracy
      limitation in its own section
- [x] Sample test results committed (raw samples, statistics, metadata, plots) — one curated
      run per device under `results/samples/`, each with its raw samples, statistics, metadata
      and its measurement-series PNG, rendered from the committed JSON so the plot provably
      belongs to that run. The unbounded `results/runs/` archive stays gitignored
- [x] `IMPLEMENTATION_NOTES.md` complete: every fix, every design decision and rejected
      alternative, every added dependency — one section per assignment section, plus
      supporting work on logging, CI, the test suite and documentation, and an open-items
      list splitting queued work from accepted costs
- [x] Automated tests in CI as a blocking gate — `pytest` over `tests/`, 98% coverage of
      `src/` against an 85% floor (`--cov-fail-under=85`). Not an assignment deliverable;
      recorded here because it gates every milestone above it
- [x] The employer's assignment brief kept out of the published repository — `Exam/` is
      gitignored and purged from history; the README describes the task in its own words
- [ ] ⏸ **Deferred** — `requirements.txt` trimmed to what is actually imported (ISS-21).
      `numpy`, `scipy`, `seaborn` and `pandas` are inherited from the supplied file and
      imported nowhere. This is the one deferred item that sits against a stated Technical
      Constraint — *minimize external library dependencies* — so the cost is real: the file
      overstates the dependency footprint. The README's *Dependencies* section lists what is
      genuinely used and names these four as unused
- [ ] ⏸ **Deferred** — manual end-to-end verification on a POSIX system. CI runs the suite on
      Linux on every pull request, so the code is exercised there; a hands-on `python main.py`
      run on macOS or Linux has not been done

---

## Future Improvements

Work that is out of scope for the assignment and was never started. It is recorded here so
the milestones above describe the delivered solution rather than an open-ended wish list.

### Observability stack

Runs are short-lived batch jobs, so a completed run would push metrics to a Prometheus
**Pushgateway**; Prometheus scrapes it and Grafana reads from Prometheus, with the whole
stack coming up from a committed `docker-compose.yml`. It would stay optional at runtime —
the framework must always produce results with the stack down. **None of this is
implemented and no metrics are exported.**

- `docker-compose.yml`, scrape config and an auto-provisioned Grafana datasource
- One shared registry behind the client, so every device is instrumented identically — call
  counter, error counter by failure kind, latency histogram, all labelled by ammeter type
- Requested vs achieved sampling rate, per-run success/failure counts, run duration and
  timing drift pushed at the end of each run
- The five statistics as labelled gauges, with a provisioned dashboard panel for each
- Run ID carried as a label, grouping keys chosen so a new run cannot overwrite the previous
  one, label cardinality documented
- A cross-device dashboard on shared normalised axes, with a side-by-side precision panel

### True accuracy assessment

The one part of the Problem Statement deliberately left unbuilt. It needs a change to the
emulators rather than to the framework: give all three devices a **common reference current**
to read, injected rather than redrawn at random on every call. With a known truth in place,
error per device becomes measurable and the existing comparison report would extend to
accuracy alongside precision. Until then the framework reports precision and says so, in the
output as well as in the documentation.

### Smaller items

- Emulator lifecycle: start/stop and clean shutdown driven from the framework (ISS-18),
  which also unblocks `SO_REUSEADDR` and removes the daemon-thread reliance (ISS-10)
- Config schema validation and a project-root-relative config path (ISS-15, ISS-19)
- `examples/run_tests.py` rewritten against the real API, or deleted (ISS-06)
- `requirements.txt` trimmed to `pyyaml`, `matplotlib` and the test-only packages (ISS-21)
- CSV export beside the JSON archive
- Per-device distribution plots, once runs carry enough samples to make shape meaningful
