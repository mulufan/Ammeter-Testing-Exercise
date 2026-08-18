# Implementation Notes

Every bug fixed, every design decision taken, and why. Written as the work happens, not
reconstructed afterwards. Bugs are catalogued in [`ISSUES.md`](ISSUES.md); this file
records what was *done* about them.

Dependencies added beyond the standard library: **none so far.**

---

## 2026-08-17 — Fix ISS-01 and ISS-02

Branch: `fix/main-commands-and-ports`. Scope was deliberately limited to these two
issues; everything else in `ISSUES.md` was left alone.

### ISS-01 — request commands were missing their flags

**Bug.** The three client calls in `main.py` sent bare device names
(`b'MEASURE_GREENLEE'`). Each emulator compares the received bytes for *exact* equality
against a command that includes flags, and `base_ammeter.py` has no `else` branch
(ISS-11), so a non-matching command produced no reply and no log line at all.

**Fix.** Each call now sends the command its device actually implements:

| Device | Command sent | Source of truth |
| --- | --- | --- |
| Greenlee | `MEASURE_GREENLEE -get_measurement` | `Greenlee_Ammeter.py:9` |
| ENTES | `MEASURE_ENTES -get_data` | `Entes_Ammeter.py:9` |
| CIRCUTOR | `MEASURE_CIRCUTOR -get_measurement -current` | `Circutor_Ammeter.py:9` |

The commands are not interchangeable and the differences are easy to miss: ENTES uses
`-get_data` where the other two use `-get_measurement`, and CIRCUTOR alone takes a second
flag, `-current`.

**Decision — the calls were uncommented.** A commented-out call cannot be verified, and
ISS-01's own acceptance criterion ("each call returns a float instead of 'No data
received'") requires the requests to be sent. This is the minimum needed to demonstrate
the fix; the rest of ISS-03 — the `time.sleep(5)` / `pass` structure, the missing return
value from the client (ISS-04), and clean shutdown — is untouched and still open.

**Known limitation.** The command strings are still hardcoded in `main.py`, duplicating
what the emulator classes define. That duplication is ISS-08's to remove by making
`config/config.yaml` the single source both sides read from.

### ISS-02 — ports disagreed across three files

**Bug.** `main.py` bound 5001/5002/5003; `README.md` and the commented block in
`config/config.yaml` both said 5000/5001/5002. Every port was shifted by one, which is
worse than a plain mismatch — `main.py`'s Greenlee port (5001) was the README's *ENTES*
port, so a client written from the documentation connected successfully to the wrong
device and received a plausible reading instead of failing. A silent wrong answer is the
worst failure mode a measurement system has.

**Fix.** Documentation was aligned to the code: **Greenlee 5001, ENTES 5002,
CIRCUTOR 5003**, updated in `README.md` and in the commented `ammeters:` block in
`config/config.yaml`. `main.py` was not changed.

**Decision, and why it reverses what `ISSUES.md` originally recommended.** The audit had
recommended adopting the documented 5000/5001/5002 on the grounds that two files agreed
and only one disagreed. That reasoning counts files instead of weighing them, and it is
wrong here:

1. **Only one of the three executes.** `main.py` binds real sockets and demonstrably
   works. The README is prose. `config.yaml`'s `ammeters:` block is *fully commented out*
   (ISS-08), so `load_config(...)['ammeters']` is `None` and the file governs nothing.
   The "majority" was two inert documents contradicting the one live implementation.
2. **Port 5000 is already taken on macOS.** AirPlay Receiver binds it by default. The
   spec requires cross-platform compatibility, so moving Greenlee to 5000 would have
   written a guaranteed `bind()` failure into the code deliberately — surfacing as
   exactly the "Address already in use" confusion ISS-10 is about. `ISSUES.md` noted this
   caveat and then recommended 5000 anyway; the caveat should have decided the question.
3. **Blast radius.** Editing documentation cannot regress runtime behaviour. Re-binding
   ports changes the one part of the system currently proven to work, and invalidates any
   per-port host firewall grants already accepted for the interpreter.

**Known limitation.** The ports are still hardcoded in `main.py` and restated in two
documents, so they can drift again. Only ISS-08 — deriving both the emulator binding and
the client target from `config.yaml` — removes that possibility. The macOS caveat should
be documented in the README once the port is genuinely overridable from config.

### ISS-24 — found while verifying, deliberately not fixed

With ISS-01 fixed, ENTES and CIRCUTOR returned readings but Greenlee still reported "No
data received." The cause was not the command or the port:
`Greenlee_Ammeter.py:15` prints the `Ω` character, this console's `sys.stdout.encoding`
is `cp1255`, and the resulting `UnicodeEncodeError` propagates out of the accept loop and
kills the emulator thread before it can reply.

Logged as [ISS-24](ISSUES.md#iss-24) and left for its own change rather than folded into
this one. It belongs with ISS-09/ISS-22 (route emulator output through a logger with an
explicit encoding), and fixing it by reconfiguring `sys.stdout` would conceal the class of
bug instead of removing it — a measurement path should not crash based on the operator's
locale.

### Verification

`PYTHONIOENCODING=utf-8 python -u main.py` (the override works around ISS-24 only; no
code was changed for it):

```
GreenleeAmmeter is running on port 5001
CircutorAmmeter is running on port 5003
EntesAmmeter is running on port 5002
Connected by ('127.0.0.1', 63680)
Greenlee Ammeter - Voltage: 6.8425700284351425V, Resistance: 16.297796925827683Ω, Current: 0.419846317853641A
Received current measurement from port 5001: 0.419846317853641 A
Connected by ('127.0.0.1', 63681)
ENTES Ammeter - Magnetic Field: 0.05842951756298435T, Calibration Factor: 1457.0511508518853, Current: 85.13479580886678A
Received current measurement from port 5002: 85.13479580886678 A
Connected by ('127.0.0.1', 63682)
CIRCUTOR Ammeter - Voltages: [...], Time Step: 0.004436110162709429s
Current: 0.02552906396929699A
Received current measurement from port 5003: 0.02552906396929699 A
```

All three devices answer, satisfying ISS-01. Each reading arrives on the port the README
and `config.yaml` now document, and the device that answers on 5001 identifies itself as
Greenlee — ISS-02's criterion that the documented port reach the intended device.

Without the encoding override, Greenlee reports "No data received." per ISS-24. The
readings also show the magnitude mismatch recorded in ISS-23 (0.42 A / 85 A / 0.026 A from
one sweep) — these devices are not measuring a shared current.

### Files touched

| File | Change |
| --- | --- |
| `main.py` | Three request commands given their flags and uncommented (ISS-01). Ports unchanged. |
| `README.md` | Ports corrected to 5001 / 5002 / 5003 (ISS-02). |
| `config/config.yaml` | Ports in the commented `ammeters:` block corrected to 5001 / 5002 / 5003 (ISS-02). Block left commented — uncommenting it is ISS-08. |
| `ISSUES.md` | ISS-01 and ISS-02 marked fixed with rationale; ISS-02's original recommendation struck through; ISS-24 added. |
| `IMPLEMENTATION_NOTES.md` | Created. |

### Open question for review

`config.yaml`'s commented CIRCUTOR entry now reads
`"MEASURE_CIRCUTOR -get_measurement -current"` while `README.md:47` still documents it
without `-current`. Both were wrong relative to the emulator; the config comment was
corrected in passing and the README deliberately was not, so the two now disagree. This
is ISS-07's territory and is parked there pending a decision on whether `-current` is a
documentation error or a flag intended to be implemented differently.

---

## 2026-08-18 — Add GitHub Actions CI for pull requests

Branch: `chore/github-actions-ci`, cut from `master` (not from the in-flight
`feature/unified-measurement-api`, so the pull request carries only CI changes). No
issue from `ISSUES.md` is fixed here; this stage adds infrastructure only.

### What CI does

`.github/workflows/ci.yml` runs on `pull_request` against `master` and on
`workflow_dispatch`. One job, `build`, on `ubuntu-latest` with Python 3.11 supplied
through a one-entry matrix: development is on Windows, so running CI on Linux exercises
the spec's cross-platform constraint rather than re-testing the dev machine. The matrix
is a single entry today purely so adding versions later is a one-line change.

Steps: checkout → `setup-python` (with pip caching keyed on `requirements.txt`) →
`pip install -r requirements.txt` → byte-compile → import check.

### Two levels of verification, deliberately

`python -m compileall` only proves the sources *parse*. That would not have caught ISS-05
(`Dict` used in `test_framework.py` but never imported), because the `NameError` fires when
the annotation is evaluated at import time, not at compile time. So there is a second step,
`scripts/ci_import_check.py`, which imports every module under `Ammeters/`, `src/` and
`examples/` plus top-level `main.py`. Importing is safe: every entry point in the repo
guards its work behind `if __name__ == "__main__":`, so no socket is bound during the check.

The script lives in the repo rather than inline in the YAML so it can be run locally
before pushing, with identical behaviour to CI.

### Why the import check is currently non-blocking

Run against `master` as it stands today:

```
OK   main
OK   Ammeters.base_ammeter
OK   Ammeters.Circutor_Ammeter
OK   Ammeters.client
OK   Ammeters.Entes_Ammeter
OK   Ammeters.Greenlee_Ammeter
FAIL src.testing.test_framework     NameError: name 'Dict' is not defined
OK   src.utils.config
OK   src.utils.logger
OK   src.utils.Utils
FAIL examples.run_tests             (same NameError, via its import)

2 module(s) failed to import.
```

Both failures are ISS-05 — `examples/run_tests.py` fails only because it imports the
broken module. This is a genuine pre-existing bug, already fixed on
`feature/unified-measurement-api` but not yet on `master`. A pull request's checks run
against the merge of the branch and its base, so a blocking import step would make this
very pull request red for a defect it does not introduce, and block its own merge.

The step therefore carries `continue-on-error: true`: the failure is visible in the log
on every pull request, but it does not gate. **When ISS-05's fix reaches `master`, delete
that one line** and the import check becomes a hard gate. `compileall` is blocking from
the start, since it passes on `master` today.

Rejected alternatives: (a) enumerating only the modules that currently import cleanly —
this hides the defect and silently under-tests as files are added; (b) fixing ISS-05 in
this branch — out of scope for a CI stage, and it would collide with the fix already
committed on the feature branch.

### No fake tests

The task explicitly excludes placeholder tests, and none were added — there is no test
suite yet, and a green `pytest` run over zero tests would assert nothing. The workflow
ends with a comment marking exactly where the `pytest` step goes when Stage 5+ produces
real tests.

### Dependencies

None added. `requirements.txt` is unchanged; CI installs it as-is (including the numpy /
scipy / matplotlib / seaborn / pandas pins that nothing imports yet — recorded in
`ISSUES.md`, not touched here). `pytest` gets added when tests do.

### Files touched

| File | Change |
| --- | --- |
| `.github/workflows/ci.yml` | New. Pull-request CI: setup Python, install deps, compile, import check. |
| `scripts/ci_import_check.py` | New. Imports every project module; non-zero exit if any fail. Runnable locally. |
| `README.md` | New "Development Workflow" section: branch → pull request → CI green → merge → delete branch, plus the local equivalents of the CI checks. |
| `IMPLEMENTATION_NOTES.md` | This entry. |
