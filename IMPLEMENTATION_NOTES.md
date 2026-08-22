# Implementation Notes

How each part of the assignment was built, the decisions behind it, and the bugs fixed on
the way. Organised by the sections of `Exam/ammeter-test-specification.md`, not by date.
Individual bugs are catalogued in [`ISSUES.md`](ISSUES.md); this file records what was
*done* about them and why.

**Dependencies beyond the standard library: none.**

| Assignment section | State |
| --- | --- |
| Groundwork — make the supplied code run | done |
| 1. Unified Measurement API | done |
| 2. Measurement Sampling | done |
| 3. Result Analysis | done |
| 4. Result Management | done |
| 5. Accuracy Assessment (bonus) | precision only — accuracy not delivered, by design |

---

## Groundwork — making the supplied code run

**What it delivers.** `python main.py` reaches all three emulators and gets a reading back.
As supplied it got nothing: the client calls were commented out, and would not have worked
if uncommented.

**Bugs fixed.** [ISS-01](ISSUES.md#iss-01) — the commented calls sent bare device names
(`b'MEASURE_GREENLEE'`), but each emulator compares the received bytes for *exact* equality
against a command that includes flags, and drops anything else without a reply
([ISS-11](ISSUES.md#iss-11)). The three commands are not interchangeable: ENTES uses
`-get_data` where the others use `-get_measurement`, and CIRCUTOR alone takes a second flag,
`-current`. [ISS-02](ISSUES.md#iss-02) — `main.py` bound 5001/5002/5003 while the README and
config said 5000/5001/5002. Every port was shifted by one, so a client written from the
documentation connected *successfully to the wrong device* and got a plausible reading. A
silent wrong answer is the worst failure mode a measurement system has.

**Decision — the documentation was aligned to the code (5001 / 5002 / 5003), not the other
way round.** Two files said 5000 and one said 5001, but counting files is the wrong test:
`main.py` is the only one of the three that executes, and port 5000 is taken by AirPlay
Receiver on macOS, so adopting it would have written a guaranteed `bind()` failure into a
project whose constraints include cross-platform support.

**Found here, fixed here.** [ISS-24](ISSUES.md#iss-24) — `Greenlee_Ammeter.py` printed the `Ω`
character, so on a console whose encoding is not UTF-8 (this machine's is `cp1255`) the
`UnicodeEncodeError` propagated out of the accept loop and killed the Greenlee thread before
it could reply. The device then refused every subsequent connection, which reads as a port or
protocol fault and is expensive to chase — ENTES and CIRCUTOR print pure ASCII and were
unaffected, so Greenlee looked individually broken. The console text now says `Ohm`.

**Decision — spell the unit, do not widen the console.** Two alternatives were rejected.
Reconfiguring `sys.stdout` to UTF-8 (or setting `PYTHONIOENCODING`) hides the class of bug
instead of removing it: a measurement path must not depend on the operator's locale, and the
next non-ASCII character added anywhere would fail the same way on a machine without the
override. Wrapping the accept loop in a blanket `except Exception` would keep the thread
alive through a crash it should not be having, and belongs with the emulator lifecycle work
([ISS-11](ISSUES.md#iss-11), [ISS-18](ISSUES.md#iss-18)) rather than being bolted on here.
The print itself is still unconditional and still floods stdout during sampling; removing it
is [ISS-22](ISSUES.md#iss-22), which waits on the logger ([ISS-09](ISSUES.md#iss-09)). This
fix makes the line safe, not absent.

**Verified.** `python main.py` on this machine's `cp1255` console, with no environment
override: five Greenlee samples and all three devices in the comparison table. The same
command before the change lost Greenlee to `UnicodeEncodeError` and ranked two devices.
`Ammeters/`, `src/` and `main.py` now contain no non-ASCII on any console path; what remains
is Hebrew comments and docstrings in `src/utils/` and `examples/`, which are never printed.

---

## 1. Unified Measurement API

**What it delivers.** One call — `AmmeterTestFramework.get_measurement(ammeter_type)` —
works for all three devices and returns the same result type for each.

**How it works.** `config/config.yaml` is the device registry: each entry carries a port and
a command string, so adding a fourth ammeter is a YAML edit rather than a code change.
`Ammeters/client.py` does one connect → send → recv, parses the reply to `float`, and either
returns it or raises. The framework wraps that float in a `Measurement`.

**Decisions.**

- **A typed `Measurement` dataclass, not a dict.** A mistyped key fails at the point of the
  mistake instead of arriving as a `None` three stages later, and `dataclasses.asdict()`
  covers the archiving stage for free. Frozen, because a sample records something that has
  already happened.
- **The timestamp is a timezone-aware UTC `datetime`.** Comparable across machines and
  across a DST change without parsing; formatting belongs at the storage boundary.
- **Failures raise; there is no `ok` / `error` field.** A result type that can mean "no
  measurement" pushes a check onto every consumer, and the consumer that forgets feeds
  `None` into `statistics.mean()`. The cost is that fault-tolerant sampling must catch per
  sample — which Stage 2 does deliberately.
- **Two exception types, not three.** `AmmeterConnectionError` (unreachable, timed out) and
  `AmmeterResponseError` (empty, non-UTF-8 or non-numeric reply) call for different caller
  behaviour; empty versus malformed does not.
- **`AmmeterError` derives from `RuntimeError` on purpose.** Response errors are raised
  inside the same `try` that guards the socket, so a base of `OSError` would see them caught
  by that handler and mislabelled as connection failures. Do not change this base class
  without re-reading this line.

**Bugs fixed.** [ISS-04](ISSUES.md#iss-04) client returned `None` instead of the reading ·
[ISS-12](ISSUES.md#iss-12) no timeout and no error handling (now `settimeout(5.0)` before
`connect()`, covering both connect and recv) · [ISS-05](ISSUES.md#iss-05) `Dict` used but
never imported, plus a relative import that broke direct execution ·
[ISS-08](ISSUES.md#iss-08) the `ammeters:` block was entirely commented out ·
[ISS-07](ISSUES.md#iss-07) README documented CIRCUTOR without `-current` ·
[ISS-19](ISSUES.md#iss-19) missing `__init__.py` in all four package directories — adding
only some is worse than adding none, since a regular package containing a namespace
subpackage resolves on some interpreters and not others.

**Verified.** One `Measurement` per device from `python main.py`, and each error path
exercised against stand-in servers replying with deliberate junk: dead port →
`AmmeterConnectionError`; wrong command (empty reply), non-numeric reply and non-UTF-8 reply
→ `AmmeterResponseError`.

---

## 2. Measurement Sampling

**What it delivers.** `collect_samples(ammeter_type)` runs a schedule described by
`measurements_count`, `total_duration_seconds` and `sampling_frequency_hz`, and returns the
list of `Measurement`s.

**How it works.** `_get_sampling_config()` resolves the configuration first, then the loop
sleeps until each sample's target time and takes one reading.

**Decisions.**

- **The three parameters are over-determined, so any two derive the third** — there is no
  precedence rule picking a winner. A precedence rule silently ignores whatever the operator
  wrote in the losing field; derivation turns a contradictory configuration into an error.
  If all three are given, they are checked for agreement.
- **The relation is `count = duration × frequency + 1`** — fencepost, not "samples per
  window": 5 samples at 2 Hz span exactly 2.0 s, the first at t=0 and the last at t=2.0.
  Worth knowing when presenting: `count=10, duration=10, frequency=1` is *rejected*, because
  10 samples at 1 Hz span 9 s.
- **Each sample is scheduled against an absolute target** (`start + index × period` off
  `time.monotonic()`), not by sleeping one period between samples. Sleeping relatively feeds
  the round-trip time of every request back into the schedule, so error accumulates;
  anchoring to the start keeps it per-sample. Monotonic, so a clock adjustment mid-run
  cannot move the schedule. Measured: 5 samples at 2 Hz completed in **2.016 s**, worst
  inter-sample error 11 ms, and not growing across the run.
- **A bad reply skips one sample; an unreachable device aborts the run.** A malformed
  reading is one lost data point; a device that has stopped answering will not start again on
  its own, and continuing would produce a run whose sample count means nothing.
- **`main.py` catches per device.** The abort policy above is deliberately blunt, so the
  caller contains it: one dead device must not take the other two down with it. ISS-24 was
  the live demonstration — it killed the Greenlee thread on a non-UTF-8 console, and the
  sweep still reported ENTES and CIRCUTOR. That bug is fixed; the guard stays, because any
  device that stops answering mid-run produces the same shape of failure.
- **Configured values are validated as positive numbers before any arithmetic** (added in
  review). Zero and negative values otherwise survive the derivation and surface much later:
  `duration=0` raised a bare `ZeroDivisionError`, `frequency=0` and `count=1` crashed inside
  the sampling loop, and `count=-3` produced an empty run with no error at all. `bool` is
  rejected explicitly, since it would otherwise pass as `int`.
- **A derived count is floored, and the duration recomputed from it** (added in review).
  `int(duration × frequency) + 1` truncated without adjusting the duration, so
  `duration=1, frequency=1.5` returned `count=2, duration=1` — a triple that fails the very
  consistency check this function applies elsewhere, and that Stage 4 would archive as run
  metadata. Flooring keeps the run inside the requested duration; the tolerance absorbs float
  representation error (`0.3 * 10` is `2.9999999999999996`).

**Bugs fixed.** [ISS-13](ISSUES.md#iss-13) — all three sampling parameters were `NULL` in
`config.yaml`, with no stated rule for which wins when more than one is supplied.

**Known limits.** Overrun is not recorded: when a round trip is longer than the period the
loop free-runs, and 50 samples requested at 1000 Hz ran at an effective 61.6 Hz with nothing
logged. Skipped samples are not tallied, so a short result list is indistinguishable from a
short configuration. Errors go to stdout via `print`, interleaving with results, until the
logger (ISS-09) is built.

**Verified.** `python main.py` — 5 samples from each of the three devices, ~0.5 s apart. The
per-device guard was verified against ISS-24 while it was still open: on a `cp1255` console
Greenlee reported `Sampling failed: ...` and the other two still delivered their samples.

---

## 3. Result Analysis

**What it delivers.** `analyze_measurements(measurements)` reduces a run to an
`AnalysisResult`: sample count, mean, median, standard deviation, min and max. Standard
library `statistics` only.

**Decisions.**

- **Sample standard deviation (`stdev`, n−1), not population (`pstdev`, n)** (changed in
  review). These are repeated readings sampling a noisy process, not an enumerated
  population, so the quantity wanted is an estimate of the process spread — and the
  unbiased estimator divides by n−1. It is also what metrology uses for Type A
  uncertainty, which matters because section 5 compares precision across devices and
  would inherit the bias. Not a rounding difference: on `[10, 20, 30, 40, 50]`, `pstdev`
  gives 14.142 against `stdev`'s 15.811, a 11.8% understatement at n=5.
- **`standard_deviation` is `None` at n=1, not `0.0`** (changed in review). `pstdev`
  returns `0.0` for a single sample, which reads as a measurement of perfect precision
  from one reading; the honest answer is that the statistic is undefined. `stdev` raises
  there, so the n=1 case is checked explicitly and the field is typed `float | None`.
  Consumers get a value that cannot be mistaken for a real spread.
- **Measurements from more than one device are rejected** (added in review). The method
  originally averaged whatever it was given: a mixed list produced
  `mean=28.475, stdev=39.97` from 85 A, 0.4 A and 0.026 A — arithmetic over three devices
  that are not measuring a shared current ([ISS-23](ISSUES.md#iss-23)). That is the exact
  failure mode section 5 has to confront, and the analysis layer was the place it became
  invisible. `AnalysisResult` now also carries `ammeter_type`, so a result is
  self-describing when section 4 archives it.
- **An empty list raises rather than returning zeros.** `collect_samples` can legitimately
  return `[]` when every read fails, and a result full of zeros would archive as though
  the run had succeeded.

**Reporting.** `AnalysisResult.__str__` renders the run as a labelled block. `main.py`
printed one per device until section 5 replaced that sweep with the cross-device comparison
table; the block is still what the archive and `examples/` render, and the mean and standard
deviation survive into the comparison, but median, min and max no longer reach the console.
Values are formatted to six significant figures rather than a fixed
decimal count: the devices read three orders of magnitude apart, so `%.2f` would show every
CIRCUTOR statistic as `0.01`. An undefined standard deviation prints as
`n/a (needs 2+ samples)`, never as a number.

**Known limits.** The metric set is hardcoded; `analysis.statistical_metrics` in
`config.yaml` is still unread. The unit from `Measurement` is dropped — `__str__` hardcodes
`A`.

**Verified.** `[10, 20, 30, 40, 50]` → mean 30.0, median 30.0, stdev 15.811, min 10.0,
max 50.0. n=1 → `standard_deviation=None`. Empty list and a mixed entes/circutor list both
raise `ValueError`. Note that this section raises the floor to **Python 3.10** (`float |
None` is evaluated at import); CI pins 3.11 and the README now states the requirement.

## 4. Result Management

**What it delivers.** `run_test(ammeter_type)` returns a `TestRunResult` — a UUID4 run ID,
start and end timestamps, the resolved sampling configuration, every raw sample and the
statistics. `src/testing/result_manager.py` archives it as one JSON file per run under
`results/runs/<test_id>.json`, and reads runs back: `save_test_run`, `load_test_run`,
`list_test_runs`, `compare_test_runs`.

**Decisions.**

- **One JSON file per run, named by run ID.** Human-readable and diffable, no index file to
  fall out of step with the directory, and a UUID4 name means a run cannot overwrite another.
  Timestamps are stored as ISO-8601 strings and parsed back to timezone-aware `datetime`s;
  `load(save(r)) == r` holds exactly, tzinfo included.
- **The whole run is archived, not just the summary.** The statistics can be recomputed from
  the samples; the samples cannot be recovered from the statistics.
- **`RESULTS_DIR` is resolved from `__file__`, not the working directory** (added in review).
  As `Path("results/runs")` it was CWD-relative, and the failure was silent in the worst way:
  run from anywhere but the repo root, `list_test_runs()` returned `[]` — indistinguishable
  from an empty archive — while `save_test_run()` quietly began a second archive tree beside
  the caller. This is ISS-15's twin; `config_path` still has it.
- **Listing returns `RunSummary` objects ordered by start time** (added in review). It
  previously returned bare UUID strings sorted lexicographically, which is an arbitrary order
  with respect to when runs happened, and carried no device, time or sample count — so
  choosing a run to retrieve meant opening every file. `RunSummary` projects only fields the
  run already computed; the storage layer calculates no new statistics.
- **One `ResultStoreError` for an archive that exists but will not read** (added in review).
  Loading previously leaked five unrelated untyped exceptions — `JSONDecodeError` on a
  truncated file, `KeyError` on a missing field, `TypeError` on an unexpected one, `ValueError`
  on an unparseable timestamp — none of them a project type. A caller facing a damaged archive
  takes the same action in every case, so the family is deliberately one class rather than a
  hierarchy, and the message names the file and the cause. A run that was never archived stays
  `FileNotFoundError`, which already says exactly that.
- **Fields are reconstructed by name, not by `SamplingConfig(**data)`** (changed in review).
  Splatting turned a field added by a later version into a `TypeError` in every older reader;
  naming the fields ignores it instead.
- **A damaged file fails a listing rather than being skipped.** Discovery that quietly drops
  unreadable runs is how an archive rots unnoticed.
- **`compare_test_runs` is presentation, not analysis.** It renders archived runs as a table
  from numbers computed at archive time and calculates nothing across runs. A selection
  spanning device types prints a warning instead of a combined figure: relative accuracy needs
  [ISS-23](ISSUES.md#iss-23) resolved first and belongs to section 5.

**What is committed, and what is ignored.** `results/runs/` is the working archive — machine
written, UUID-named and unbounded — so it is gitignored along with `results/logs/`; committing
it would put every local run into the diff and grow the repo without limit. `results/samples/`
holds one curated run per device and *is* tracked, because sample test results are an
assignment deliverable, they let a reviewer see the archive format without running anything,
and fixed data makes the section 5 comparison and any committed plots reproducible. No code
change was needed to write there: `results_dir` is already a parameter on every storage
function. The ignore rule is `results/*` rather than `results/` because git does not descend
into an excluded directory, so a `!results/samples/` negation under `results/` would never be
reached.

**The metrics stack does not change this.** Prometheus and Grafana are a separate bonus and
are not a consumer of these files: the roadmap design pushes a finished run's statistics to a
Pushgateway, Prometheus scrapes that, and Grafana reads from Prometheus — never from JSON on
disk, and never from git. The two sinks also hold different things. Prometheus stores labelled
metric series, not the raw per-sample readings with their own capture timestamps, so the JSON
archive stays the system of record and Grafana is a derived view of it. That is also why the
framework is required to produce complete results with the stack down. Matplotlib plots
(section 3 bonus) read the local archive at runtime, likewise not the committed copy.

**Known limits.** `save_test_run` writes in place, so a crash mid-write leaves a truncated
file — caught cleanly on load now, but an atomic temp-file-plus-replace would prevent it.
The archive carries no schema version. `result_management:` in `config.yaml` is still an empty
key; the results path is a module constant while ports, commands and sampling are config-driven.
`list_test_runs` loads each run in full to summarise it, which is irrelevant at this scale and
would not be at thousands of runs.

**Verified.** Round trip exact against a real archived run (`load(save(r)) == r`, tz-aware
timestamps preserved). Discovery from a foreign working directory: 3 runs found, where the
pre-fix code returned `[]`. Ordering proven on three runs whose IDs sort in the exact inverse
of their start times — output is chronological. All six corruption cases (truncated JSON,
missing `analysis`, missing `unit`, unparseable timestamp, null timestamp, unknown extra
field) resolve as one `ResultStoreError` naming the file, except the extra field, which now
loads by design; a missing run still raises `FileNotFoundError`. Mixed-device comparison
emits its warning; empty comparison raises `ValueError`.

## 5. Accuracy Assessment (bonus) — delivered as precision only

**What it delivers.** `evaluate_precision(analysis)` reduces an `AnalysisResult` to a
`PrecisionResult` — device, sample count, mean, standard deviation and coefficient of
variation. `rank_precision` orders those least-variable-first, and `compare_precision`
renders every device as one ranked table with the caveats that make it readable. `main.py`
sweeps the config registry and prints that table.

**The central decision: precision, not accuracy.** The section is named *Accuracy
Assessment*, and the accuracy half is deliberately not implemented. Accuracy is distance
from a true value; the three emulators expose no shared reference current, and they are not
measuring one physical quantity ([ISS-23](ISSUES.md#iss-23)). Any accuracy figure would
have required inventing the truth it was measuring against. What *can* be quantified
honestly is dispersion, so that is what the section reports, and the report says so in as
many words rather than leaving a reader to infer it.

**Why the coefficient of variation.** `stdev / |mean|` is dimensionless, which is the whole
point: the devices read three orders of magnitude apart, so ranking on raw standard
deviation ranks them by magnitude rather than by consistency. CV is the standard named
technique for exactly this — comparing dispersion between variables on different scales —
which also satisfies the "named statistical technique" requirement without adding a
dependency. Section 3 already chose the sample standard deviation (n−1) partly in
anticipation of this, so no bias is inherited here.

**Decisions.**

- **`sample_count` travels on `PrecisionResult`** (added in review). A CV from 5 samples and
  a CV from 500 are not comparable evidence, and without the count nothing downstream —
  including a human reading the table — can tell them apart.
- **Undefined CVs stay in the ranking** (changed in review). `rank_precision` first sorted
  the comparable results and returned only those, so a device sampled once vanished from the
  report with nothing saying a device was missing. It now sorts on
  `(cv is None, cv or 0.0)`, which partitions the undefined ones to the end and keeps them
  visible as `N/A`. Same principle as `list_test_runs` refusing to skip damaged runs.
- **The caveats are part of the report, not of the documentation.** `compare_precision`
  appends three notes: that this ranks variability and not accuracy, that the spread belongs
  to each device's model rather than to an instrument, and that a CV from few samples is
  unstable. A ranked table headed by a device name invites "the winner is the better
  instrument" — the one conclusion these numbers cannot support — and a caveat that lives
  only in a Markdown file does not travel with the output. `compare_test_runs` set the
  precedent in section 4.
- **No "most reliable device" is declared.** The roadmap item asks for one. Ranking is
  reported and naming a winner is not, because at the sample counts a default run collects
  the gaps are routinely smaller than the noise (below). Declaring a winner would need a
  separability test, which was considered and cut as over-engineering for a bonus section.
- **Table headers are generated from the column widths.** They were written out by hand and
  every header sat one character right of its own column.

**The limitation that shapes the whole section.** These emulators redraw their physical
parameters on *every* call, so consecutive samples are independent draws from a random
model, not repeated readings of one current. Precision in metrology is measured under
repeatability conditions — same measurand, repeated reads — and this setup cannot provide
them without modifying the emulators. So the CV here describes the spread of each device's
generator, and the resulting order is a fixed property of those generators rather than a
finding about hardware. CIRCUTOR always wins because `sum` over 10 terms averages variance
down by √10; Greenlee always loses because `V/R` with `R∈[0.1,100]` is a heavy-tailed ratio
distribution. Simulating the three models over 200 000 draws gives the true values:

| Device | Model | True CV |
| --- | --- | --- |
| CIRCUTOR | Σ(V·Δt), 10 terms | 0.222 |
| ENTES | B·K | 0.607 |
| Greenlee | V/R | 5.007 |

**Sample count is what makes the ranking mean anything.** With `measurements_count: 5` the
sampling distribution of the sample CV is so wide that all three devices overlap, and an
observed sweep gave entes 51.19%, circutor 51.25%, greenlee 52.14% — a spread of under one
percentage point, and an order (`entes < circutor < greenlee`) that is *wrong* against the
true values above. 90% ranges from 20 000 simulated runs per device:

| Device | n=5 | n=50 |
| --- | --- | --- |
| CIRCUTOR | [0.096, 0.344] | [0.185, 0.259] |
| ENTES | [0.287, 0.907] | [0.520, 0.698] |
| Greenlee | [0.375, 1.937] | [1.084, 4.759] |

At n=50 the ranges are disjoint and the order is stable and correct. The configured default
is still 5, which is a demo-speed choice rather than a measurement choice; the third caveat
in the report warns against reading a narrow gap, and raising the count to
`50 / 4.9 s / 10 Hz` is the fix when the number needs to mean something. Greenlee's CV stays
conservative even at n=500 (median 3.97 against a true 5.007) because of that tail — the
ordering is right, the magnitude is understated.

**Rejected alternatives.**

- **Analytic reference currents, and bias against them.** Each emulator's expected value is
  exactly derivable — Greenlee `5.5·ln(1000)/99.9 = 0.380307 A`, ENTES `0.055·1250 =
  68.75 A`, CIRCUTOR `10·0.55·0.0055 = 0.03025 A` — which would have made
  `(mean − reference)/reference` a real accuracy figure and ticked the roadmap's *relative
  accuracy* box. Rejected: it measures whether the sampling pipeline reproduces a
  distribution the emulator declares, which is a self-consistency check dressed as accuracy.
  A reader would take a "bias" column as a statement about the device. The honest version
  needs a reference the device does not supply.
- **Standard error on the CV** (`CV/√(2(n−1))`), to mark two devices as indistinguishable.
  Correct in principle and the right long-term answer, but it is the normal approximation and
  these distributions are skewed enough that it would be optimistic where it matters most.
  Raising the sample count solves the same problem without shipping a number that is wrong
  in the Greenlee case.
- **A `Protocol` so archived `RunSummary` objects feed the assessment directly.** Deferred.
  It is the right seam once cross-run comparison is wanted; today every caller has an
  `AnalysisResult` in hand and the abstraction would have no second implementation.
- **A separate `src/testing/accuracy.py`.** The three methods sit on `AmmeterTestFramework`
  next to `analyze_measurements`, which is where a caller looks for them. Worth splitting out
  if the section grows.

**Known limits.** No accuracy, by design. No winner is named. `main.py` no longer prints the
per-device `AnalysisResult` block — median, min and max are computed and archived but absent
from the console sweep, which now shows only the comparison table. The report is text only;
the visualisation bonus is unstarted.

**Verified.** A full sweep with all three emulators alive ranks entes 27.32%, greenlee
57.42%, circutor 57.84% at n=5 — the near-tie the caveat warns about. The single-device-down
path was verified against [ISS-24](ISSUES.md#iss-24) while it was open: on a non-UTF-8
Windows console the sweep printed `Skipping greenlee: …` and still produced the table for the
other two, where before the `except (AmmeterError, ValueError)` guard the same command died
with an unhandled `AmmeterConnectionError` and printed nothing at all. With ISS-24 fixed the
same console now ranks all three. `compare_precision([])` raises
`ValueError`. A device with `standard_deviation=None` renders as `N/A` and sorts last; a
device with `CV=0.0` sorts first rather than being confused with an undefined one. Columns
line up under their headers. `compileall` and `scripts/ci_import_check.py` both clean.

---

## Supporting work — continuous integration

`.github/workflows/ci.yml` runs on every pull request to `master`: install requirements,
byte-compile every source file, then import every module via `scripts/ci_import_check.py`.
Both steps exist because `compileall` only proves the sources *parse* — it would not have
caught ISS-05, whose `NameError` fires when the annotation is evaluated at import time. CI
runs on Linux while development is on Windows, which is what actually exercises the
cross-platform constraint.

The import step carried `continue-on-error: true` because ISS-05 was still unfixed on
`master` when CI was added, and a blocking step would have made that pull request red for a
defect it did not introduce. That fix has since merged, so the line is gone and both steps
are hard gates.

No placeholder tests were added — a green `pytest` run over zero tests asserts nothing. The
workflow marks where the `pytest` step goes when Stage 3 produces real tests.

---

## Open items

Split by intent. **Queued** items are work still meant to happen; **⏸ deferred** items were
taken off the work list by the [triage in `ISSUES.md`](ISSUES.md#triage-2026-08-22) and are
recorded as accepted costs, not as a backlog. The distinction matters when reading this file
later: a known limitation that someone decided to keep is a different statement from one
nobody has got to yet.

**⏸ Deferred.**

- `config_path` is CWD-relative and the config is never validated against a schema
  ([ISS-15](ISSUES.md#iss-15)), so the framework runs from the repo root only. The path fix
  and the missing-file handling were kept together deliberately rather than landing half in
  two places; deferring one defers both, along with the remaining half of
  [ISS-19](ISSUES.md#iss-19).
- `main.py` keeps the supplied `sleep(5)`. The trailing `pass` is gone, but removing the
  sleep needs a readiness signal, which is [ISS-18](ISSUES.md#iss-18) and deferred. Five
  seconds of startup on a program that then runs for two is the accepted cost.
  [ISS-10](ISSUES.md#iss-10) is *not* deferred and removes the other reason the sleep exists.
- An exception raised inside `measure_current()` still escapes the accept loop and kills the
  emulator thread for the rest of the process ([ISS-18](ISSUES.md#iss-18)). ISS-24 was one
  way to trigger it; the loop has no error boundary of its own. This is the deferral with the
  sharpest edge — a device can still die mid-run — mitigated by `main.py` catching per device
  so the other two finish.
- The emulators still `print()` their internals on every measurement
  ([ISS-22](ISSUES.md#iss-22)): stdout floods during a run, and the write sits inside the loop
  whose timing section 2 measures. Worth folding into the ISS-09 logger branch if it is cheap
  there.

**Queued.**

- `main.py` still hardcodes the ports it *binds*, so `config.yaml` is the single source of
  truth for the client half only ([ISS-08](ISSUES.md#iss-08)).
- The default `measurements_count: 5` is a demo-speed setting, not a measurement one: at
  n=5 the coefficient of variation is too noisy to separate the three devices (section 5).
  Raising it to `50 / 4.9 s / 10 Hz` is the fix when the ranking needs to mean something.
- `AmmeterResponseError` names the port but not the offending payload — recoverable from the
  chained traceback, absent from the line an operator actually reads.
- `analysis.statistical_metrics`, `analysis.visualization.plot_types` and `result_management:`
  are still empty keys that parse to `None`, and the analysis layer hardcodes its metric set
  ([ISS-13](ISSUES.md#iss-13), the half of it that is not fixed).
