# Roadmap

A living document. Check off items as they ship. Add new items under the relevant
milestone or create a new one. Last updated: 2026-08-17.

Observability is not a separate phase — every milestone carries its own metrics work,
marked **Observability:**. Runs are short-lived batch jobs, so each completed run pushes
its metrics to a Prometheus **Pushgateway**; Prometheus scrapes the gateway and Grafana
reads from Prometheus. The whole stack comes up from a committed `docker-compose.yml`.
The stack is optional at runtime: the framework must always produce results with it down.

---

## 🟡 Milestone 1 — Bootstrap & Existing Bugs Fixed

- [x] Repository audited — every supplied source file read and its current responsibility documented
- [x] All bugs, mismatches and unimplemented pieces in the supplied code catalogued
- [ ] Port assignments reconciled across `main.py`, `config/config.yaml` and `README.md` (one source of truth)
- [ ] Command strings sent by clients match what each emulator expects (`-get_measurement`, `-get_data`, `-get_measurement -current`)
- [ ] `README.md` CIRCUTOR command corrected to `MEASURE_CIRCUTOR -get_measurement -current`
- [ ] `request_current_from_ammeter()` returns the parsed reading instead of only printing it
- [ ] Client parses the socket reply into a `float` and validates it
- [ ] Client handles connection refusal and timeout without hanging or raising an unhandled exception
- [ ] Emulator sockets set `SO_REUSEADDR` so servers restart cleanly between runs
- [ ] Emulators reply with an explicit error instead of silently dropping an unrecognised command
- [ ] `src/testing/test_framework.py` imports cleanly (missing `Dict` import fixed)
- [ ] `examples/run_tests.py` calls `run_test()` with its required argument
- [ ] `src/utils/logger.py` actually writes to `results/logs/` (handler, formatter and level attached)
- [ ] `load_config()` opens files with an explicit UTF-8 encoding
- [ ] `python main.py` runs end to end and prints a real current reading from all three ammeters
- [ ] `IMPLEMENTATION_NOTES.md` created and recording each fix as it lands
- [ ] **Observability:** `docker-compose.yml` at the repo root brings up Prometheus, Pushgateway and Grafana with a single command
- [ ] **Observability:** `prometheus.yml` scrape config committed; Prometheus confirmed scraping the Pushgateway target as UP
- [ ] **Observability:** Grafana auto-provisions Prometheus as a datasource on startup — no manual clicking in the UI
- [ ] **Observability:** `prometheus_client` added to `requirements.txt`, with the added dependency justified in `IMPLEMENTATION_NOTES.md` against the spec's "minimize dependencies" constraint

## ⬜ Milestone 2 — Unified Measurement API

- [ ] One client abstraction exposes a single measurement call that works for Greenlee, ENTES and CIRCUTOR
- [ ] All three devices return the same result type (value, unit, timestamp, device id, success flag)
- [ ] Failures surface as one consistent error type regardless of which device produced them
- [ ] Ammeter definitions (name, port, command) are read from `config/config.yaml` — nothing hardcoded
- [ ] The `ammeters:` block in `config.yaml` is uncommented and fully populated
- [ ] Adding a fourth ammeter needs only a config entry plus an emulator class — no framework edits
- [ ] Emulator start/stop is controllable from the framework, not only from `main.py`
- [ ] A device that is unreachable is reported clearly instead of stalling the caller
- [ ] **Observability:** a single shared metrics registry sits behind the unified client, so all three devices are instrumented identically by construction
- [ ] **Observability:** every measurement call increments a counter labelled by ammeter type
- [ ] **Observability:** connection, timeout and parse failures increment a labelled error counter distinguishable by failure kind
- [ ] **Observability:** per-call latency recorded as a histogram, labelled by ammeter type

## ⬜ Milestone 3 — Measurement Sampling

- [ ] Sampling by an explicit number of measurements
- [ ] Sampling bounded by a total test duration
- [ ] Sampling at a configured frequency (Hz)
- [ ] Precedence rule defined and documented for when count / duration / frequency are combined
- [ ] Timing uses a monotonic clock and does not accumulate drift over a long run
- [ ] Achieved sampling rate reported alongside the requested rate for every run
- [ ] A failed or dropped sample is recorded and the run continues rather than aborting
- [ ] Sampling parameters are read from `config.yaml` with no `NULL` placeholders left
- [ ] **Observability:** requested vs achieved sampling rate pushed as gauges at the end of each run
- [ ] **Observability:** per-run sample success and failure counts pushed to the gateway
- [ ] **Observability:** total run duration pushed as a gauge
- [ ] **Observability:** timing drift (scheduled vs actual sample instant) exported so the precision claim is evidenced, not asserted

## ⬜ Milestone 4 — Result Analysis

- [ ] Mean current computed per run
- [ ] Median current computed per run
- [ ] Standard deviation computed per run
- [ ] Minimum and maximum computed per run
- [ ] Sample count and failure count reported next to the statistics
- [ ] Consistency / variability metric reported (e.g. coefficient of variation)
- [ ] Statistics computed with the standard library unless an added dependency is justified in writing
- [ ] Run summary printed in a clear, readable format
- [ ] (Bonus) Measurement series plotted over time with matplotlib and saved alongside the run
- [ ] (Bonus) Per-ammeter distribution / histogram plot saved alongside the run
- [ ] **Observability:** mean, median, standard deviation, min and max pushed as labelled gauges for every run
- [ ] **Observability:** a Grafana dashboard panel for each statistic, committed as provisioned JSON rather than hand-built in the UI
- [ ] **Observability:** dashboard verified to render correctly for a run of each of the three ammeter types
- [ ] **Observability:** static matplotlib plots remain the committed sample-results artefact — Grafana complements them, it does not replace them

## ⬜ Milestone 5 — Result Management

- [ ] Every test run is assigned a unique run ID
- [ ] Run metadata stored: timestamp, ammeter type, sampling configuration
- [ ] Raw samples persisted, not only the computed summary
- [ ] Results written to a predictable location under `results/`
- [ ] Past runs can be listed
- [ ] A specific past run can be retrieved by its ID
- [ ] Two or more past runs can be compared side by side
- [ ] Storage format is portable and human-readable (JSON and/or CSV)
- [ ] **Observability:** the run ID travels as a Prometheus label so every pushed metric maps back to its archived run on disk
- [ ] **Observability:** Pushgateway grouping keys chosen so a new run does not overwrite the previous run's metrics
- [ ] **Observability:** Grafana can filter and compare historical runs by run ID
- [ ] **Observability:** label cardinality considered and documented — run IDs as labels must not grow unbounded

## ⬜ Milestone 6 — Accuracy Assessment (Bonus)

- [ ] Runs from different ammeter types compared within a single report
- [ ] The differing measurement magnitudes across devices handled explicitly (normalised, or an agreed reference stated)
- [ ] Relative accuracy quantified per device
- [ ] Measurement precision quantified using a named statistical technique
- [ ] Most reliable measurement method identified, with the reasoning recorded
- [ ] (Bonus) Error simulation available to exercise the comparison
- [ ] **Observability:** cross-ammeter comparison dashboard plotting all three devices on shared, normalised axes
- [ ] **Observability:** precision / variability panel showing spread per device side by side
- [ ] **Observability:** simulated error conditions visibly show up on the dashboard as a distinguishable signal

## ⬜ Milestone 7 — Documentation & Polish

- [ ] `README.md` project structure matches the real repo layout (every path and filename correct)
- [ ] `README.md` ports and commands match the code exactly
- [ ] Install instructions present: Python version, virtual environment, `pip install -r requirements.txt`
- [ ] Usage instructions present: start the emulators, run a test, find the results
- [ ] `requirements.txt` lists only packages actually imported by the project
- [ ] Sample test results committed to the repository
- [ ] `IMPLEMENTATION_NOTES.md` documents every bug fixed and the reasoning behind each fix
- [ ] `IMPLEMENTATION_NOTES.md` documents design decisions and the alternatives rejected
- [ ] `IMPLEMENTATION_NOTES.md` lists every dependency added beyond the standard library
- [ ] Verified to run on Windows and on at least one POSIX system
- [ ] No leftover debug printing that floods stdout during high-frequency sampling
- [ ] **Observability:** `README.md` documents bringing the stack up, the ports it exposes, and where to find the dashboard
- [ ] **Observability:** Grafana dashboard JSON committed under version control and provisioned automatically on startup
- [ ] **Observability:** verified that the framework runs and produces complete results with the stack shut down — monitoring is never a hard dependency
- [ ] **Observability:** a screenshot of the populated dashboard included with the sample results
- [ ] **Observability:** `IMPLEMENTATION_NOTES.md` explains the Pushgateway choice (short-lived batch runs) over a scraped `/metrics` endpoint
