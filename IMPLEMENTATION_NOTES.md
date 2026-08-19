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
| 3. Result Analysis | not started |
| 4. Result Management | not started |
| 5. Accuracy Assessment (bonus) | not started |

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

**Found here, still open.** [ISS-24](ISSUES.md#iss-24) — `Greenlee_Ammeter.py` prints the `Ω`
character, so on a console whose encoding is not UTF-8 (this machine's is `cp1255`) the
`UnicodeEncodeError` propagates out of the accept loop and kills the Greenlee thread before
it can reply. Run with `PYTHONIOENCODING=utf-8` until it is fixed. It belongs with the
logger work (ISS-09 / ISS-22); reconfiguring `sys.stdout` would hide the class of bug rather
than remove it — a measurement path should not fail based on the operator's locale.

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
- **`main.py` catches per device.** ISS-24 kills the Greenlee thread on a non-UTF-8 console,
  and without the per-device catch that one dead device would take the other two down with
  it — the abort policy above is deliberately blunt, so the caller contains it.
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

**Verified.** `python main.py` — 5 samples from each of the three devices, ~0.5 s apart.
Under `PYTHONIOENCODING=cp1255`, Greenlee reports `Sampling failed: ...` per ISS-24 and the
other two still deliver their samples.

---

## 3. Result Analysis — not started

Mean, median, standard deviation, min and max over a run, via the standard-library
`statistics` module. Visualisation and consistency evaluation are the bonus half.

## 4. Result Management — not started

Unique run IDs, metadata, on-disk archiving, retrieval and comparison of historical runs.

## 5. Accuracy Assessment (bonus) — not started

Cross-device comparison has to confront [ISS-23](ISSUES.md#iss-23) first: the three
emulators produce non-comparable magnitudes (roughly 0.4 A / 85 A / 0.026 A in one sweep),
so they are not measuring a shared current and a naive accuracy comparison would be
meaningless without normalisation or a stated reference.

---

## Supporting work — continuous integration

`.github/workflows/ci.yml` runs on every pull request to `master`: install requirements,
byte-compile every source file, then import every module via `scripts/ci_import_check.py`.
Both steps exist because `compileall` only proves the sources *parse* — it would not have
caught ISS-05, whose `NameError` fires when the annotation is evaluated at import time. CI
runs on Linux while development is on Windows, which is what actually exercises the
cross-platform constraint.

The import step carries `continue-on-error: true` because ISS-05 was still unfixed on
`master` when CI was added, and a blocking step would have made that pull request red for a
defect it did not introduce. **Once the ISS-05 fix is merged to `master`, delete that line**
and the check becomes a hard gate.

No placeholder tests were added — a green `pytest` run over zero tests asserts nothing. The
workflow marks where the `pytest` step goes when Stage 3 produces real tests.

---

## Open items

- `config_path` is CWD-relative and the config is never validated against a schema
  ([ISS-15](ISSUES.md#iss-15)) — the path fix and the missing-file handling should land
  together rather than half in two places.
- `main.py` still hardcodes the ports it *binds*, so `config.yaml` is the single source of
  truth for the client half only ([ISS-08](ISSUES.md#iss-08)).
- `main.py` keeps the supplied `sleep(5)` and trailing `pass`; removing them needs a
  readiness signal and a shutdown path ([ISS-10](ISSUES.md#iss-10),
  [ISS-18](ISSUES.md#iss-18)), not just deletion.
- `AmmeterResponseError` names the port but not the offending payload — recoverable from the
  chained traceback, absent from the line an operator actually reads.
- ISS-24 (the `Ω` print) is unfixed; Greenlee needs `PYTHONIOENCODING=utf-8` on a non-UTF-8
  console.
