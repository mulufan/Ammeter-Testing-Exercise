# Known Issues in the Supplied Code

Findings from a full read of the supplied repository, before any code was changed.
The assignment states: *"Use existing ammeter emulation infrastructure — if you get an
error in the code, please fix it, and explain the fix in the documentation."* This file
is the catalogue of what is wrong. Each fix, once applied, is explained in
`IMPLEMENTATION_NOTES.md`.

Last updated: 2026-08-22. **Status: ISS-01, ISS-02, ISS-04, ISS-05, ISS-07, ISS-08,
ISS-12, ISS-23 and ISS-24 fixed. ISS-13 and ISS-19 partially addressed. Everything else in
the must-fix list still open.**

**Severity:** 🔴 Blocker (nothing works until fixed) · 🟠 High (wrong or misleading
behaviour) · 🟡 Medium (fragile, will bite under load or on another OS) · ⚪ Low (polish)

**Status:** ☐ open · ◐ partially fixed · ☑ fixed · ⏸ deferred

---

## Triage (2026-08-22)

The catalogue below is the *audit*: everything the read of the supplied repository turned up,
kept whole. It is deliberately not the same thing as the work list. Six findings have been
moved to **[deferred](#summary--deferred-nice-to-have)** — real, correctly diagnosed, and judged not
worth the change against the remaining time. They are latent fragilities rather than active
faults: nothing in them produces a wrong measurement or a wrong statistic today.

Nothing was deleted. An audit that quietly drops its own findings cannot be told apart from
an audit that missed them, and the assignment asks for the bugs to be found and explained,
not only for the code to end up working. Each deferred entry keeps its ID, its anchor and its
diagnosis, and carries a note saying what accepting it costs.

Two entries the first pass of this triage put in the deferred pile were pulled back:

- **[ISS-21](#iss-21)** — *"minimize external library dependencies"* is a stated Technical
  Constraint in the specification, so this one is graded directly, and the fix is deleting
  four lines from `requirements.txt`.
- **[ISS-16](#iss-16)** — correlated pseudo-random data undermines the statistics that are
  the entire deliverable. Also a three-line fix.

## Summary — must fix

| ID | Area | Issue | Severity | Status |
| --- | --- | --- | --- | --- |
| [ISS-01](#iss-01) | `main.py` | Commented request commands are missing their flags | 🔴 | ☑ |
| [ISS-02](#iss-02) | Ports | README ports are shifted by one from the actual ports | 🔴 | ☑ |
| [ISS-03](#iss-03) | `main.py` | Script exits immediately and returns no data | 🔴 | ◐ |
| [ISS-04](#iss-04) | `client.py` | `request_current_from_ammeter()` returns nothing | 🔴 | ☑ |
| [ISS-05](#iss-05) | `test_framework.py` | `Dict` used but never imported — module cannot import | 🔴 | ☑ |
| [ISS-06](#iss-06) | `run_tests.py` | `run_test()` called with no argument | 🔴 | ☐ |
| [ISS-07](#iss-07) | README | CIRCUTOR command documented without `-current` | 🟠 | ☑ |
| [ISS-08](#iss-08) | `config.yaml` | Entire `ammeters:` block commented out | 🟠 | ☑ |
| [ISS-09](#iss-09) | `logger.py` | Logger never attaches a handler — nothing is logged | 🟠 | ☐ |
| [ISS-10](#iss-10) | `base_ammeter.py` | No `SO_REUSEADDR` — restart fails with "address in use" | 🟠 | ☐ |
| [ISS-11](#iss-11) | `base_ammeter.py` | Unknown commands dropped silently, client hangs | 🟠 | ☐ |
| [ISS-12](#iss-12) | `client.py` | No socket timeout and no error handling | 🟠 | ☑ |
| [ISS-13](#iss-13) | `config.yaml` | All sampling parameters are `NULL` | 🟠 | ◐ |
| [ISS-14](#iss-14) | README | Documented file paths and names do not exist | 🟡 | ☐ |
| [ISS-16](#iss-16) | `base_ammeter.py` | Global RNG reseeded per instance; correlated sequences | 🟡 | ☐ |
| [ISS-21](#iss-21) | `requirements.txt` | Five heavy dependencies, only one is imported | 🟡 | ☐ |
| [ISS-23](#iss-23) | Design | Devices produce non-comparable magnitudes | 🟡 | ☑ |
| [ISS-24](#iss-24) | `Greenlee_Ammeter.py` | `Ω` in `print()` kills the thread on a non-UTF-8 console | 🔴 | ☑ |

## Summary — deferred (nice to have)

Found, diagnosed, and consciously not scheduled. The last column is what accepting each one
costs, so the decision can be re-read later rather than re-argued.

| ID | Area | Issue | Severity | Cost of leaving it |
| --- | --- | --- | --- | --- |
| [ISS-15](#iss-15) | `config.py` | File opened without explicit encoding; no validation | 🟡 | Framework runs only from the repo root; a non-ASCII config would mis-decode on Windows |
| [ISS-17](#iss-17) | `base_ammeter.py` | Exact byte compare on a single `recv()` | 🟡 | A split TCP segment or a trailing newline reads as an unknown command |
| [ISS-18](#iss-18) | `base_ammeter.py` | Servers cannot be stopped; one client at a time | 🟡 | Blocks the structural half of ISS-03 and the framework-controlled emulator lifecycle |
| [ISS-19](#iss-19) | Packaging | No `__init__.py`; imports depend on the working directory | 🟡 | `__init__.py` done; the CWD-relative `config_path` remains, with ISS-15 |
| [ISS-20](#iss-20) | Protocol | Reply has no framing or delimiter | 🟡 | Same class as ISS-17; safe only because replies are short and loopback is reliable |
| [ISS-22](#iss-22) | Emulators | Unconditional `print()` on every measurement | ⚪ | stdout floods during a run, and the I/O sits inside the timed sampling loop |

---

## 🔴 Blockers

### ISS-01
**Commented request commands in `main.py` are missing their flags**

*Location:* `main.py:33-35`

The commented-out client calls send bare command names. Every emulator requires the
full command string including its flags, so all three requests are ignored.

```python
# current — main.py:33-35
# request_current_from_ammeter(5001, b'MEASURE_GREENLEE')   # Request from Greenlee Ammeter
# request_current_from_ammeter(5002, b'MEASURE_ENTES')      # Request from ENTES Ammeter
# request_current_from_ammeter(5003, b'MEASURE_CIRCUTOR')   # Request from CIRCUTOR Ammeter
```

The emulators compare the received bytes for exact equality against:

| Device | Required command | Defined in |
| --- | --- | --- |
| Greenlee | `MEASURE_GREENLEE -get_measurement` | `Ammeters/Greenlee_Ammeter.py:9` |
| ENTES | `MEASURE_ENTES -get_data` | `Ammeters/Entes_Ammeter.py:9` |
| CIRCUTOR | `MEASURE_CIRCUTOR -get_measurement -current` | `Ammeters/Circutor_Ammeter.py:9` |

Note all three differ: Greenlee and CIRCUTOR use `-get_measurement` where ENTES uses
`-get_data`, and CIRCUTOR takes a second flag `-current`.

*Required fix:* send the full command for each device — `b'MEASURE_GREENLEE -get_measurement'`,
`b'MEASURE_ENTES -get_data'`, `b'MEASURE_CIRCUTOR -get_measurement -current'` — and take
the strings from config rather than hardcoding them a second time (see ISS-08).

*Verify:* each call returns a float instead of the client reporting "No data received."

**☑ Fixed.** The three calls now carry their full command strings and were uncommented —
a commented-out call cannot be verified, and the issue's own verification criterion
requires the requests to actually be sent. Sourcing the strings from config is deferred
with ISS-08; the ports and commands are still hardcoded here, so this is a corrected
duplicate rather than a single source of truth. The trailing `pass` went with section 5,
which gave `main.py` a real body; the remainder of ISS-03 (the `sleep(5)` and clean
shutdown) is untouched and still open.

---

### ISS-02
**README ports are shifted by one from the ports actually used**

*Location:* `main.py:11,15,19` vs `README.md:32,39,46` vs `config/config.yaml:9,12,15`

| Device | README says | `config.yaml` (commented) says | `main.py` actually binds |
| --- | --- | --- | --- |
| Greenlee | 5000 | 5000 | **5001** |
| ENTES | 5001 | 5001 | **5002** |
| CIRCUTOR | 5002 | 5002 | **5003** |

Every port is shifted by one. This is worse than a plain mismatch: `main.py`'s Greenlee
port (5001) is the README's **ENTES** port, so a client written from the README connects
successfully to the *wrong device* and receives a plausible-looking current reading
rather than failing cleanly. A silent wrong answer in a measurement system is the most
dangerous failure mode there is.

*Required fix:* pick one source of truth — `config/config.yaml` — and derive both the
emulator binding and the client target from it, so the three files cannot drift again.

~~Recommend adopting the documented **5000 / 5001 / 5002**, since README and `config.yaml`
already agree and only `main.py` disagrees.~~ **This recommendation was wrong and has been
reversed — see the fix note below.**

*Caveat worth documenting:* on macOS, port **5000** is occupied by the AirPlay Receiver
service by default. Since the spec requires cross-platform compatibility, the port must
be overridable from config and that override documented in the README.

*Verify:* README, `config.yaml` and the running processes all agree; requesting the
Greenlee port returns a reading whose printed device name is Greenlee.

**☑ Fixed — by aligning the documentation to the code (5001 / 5002 / 5003), not the
reverse.** The original recommendation counted files rather than weighing them. Of the
three, only `main.py` executes: the README is prose and `config.yaml`'s `ammeters:` block
is entirely commented out (ISS-08), so it parses to `None` and governs nothing. The
"majority" was two inert documents disagreeing with the one working implementation.

The caveat above then decides it: adopting 5000 would have made Greenlee collide with
macOS AirPlay Receiver by default, writing a known cross-platform failure into the code on
purpose. Editing prose also cannot regress behaviour, whereas re-binding ports changes the
only part of the system currently proven to work and invalidates per-port host firewall
grants.

Still open: the underlying duplication. Ports remain hardcoded in `main.py` and restated in
two documents; only ISS-08 removes the possibility of drift.

---

### ISS-03
**`main.py` exits immediately and returns no data**

*Location:* `main.py:32-37`

After `time.sleep(5)` the script reaches `pass` and terminates. The emulator threads are
daemons, so they are killed on exit. Running `python main.py` therefore starts three
servers, waits five seconds, and prints nothing.

The assignment requires: *"make the main.py script work and return data from the ammeters."*

*Required fix:* after the servers are up, perform a real measurement against each device
and print the result; keep the process alive while doing so.

*Verify:* `python main.py` prints one current reading per ammeter and exits cleanly.

**◐ Partially fixed.** The verification criterion above passes — `main.py` calls
`AmmeterTestFramework.get_measurement()` for each device and prints three `Measurement`s, and
the trailing `pass` is gone. The structural half is untouched: the fixed `time.sleep(5)` is
still there. The sleep is a workaround for ISS-10 (`SO_REUSEADDR`) and the absence of a
readiness signal (ISS-18); deleting it without those replaces a slow start with a race.

*Triage note (2026-08-22):* ISS-10 stays on the must-fix list, but ISS-18 is now deferred, so
the readiness signal is not coming. The `sleep(5)` therefore stands as an accepted cost — five
seconds of startup on a program that then runs for two — rather than as work still queued. If
that is not acceptable, ISS-18 has to come back with it.

---

### ISS-04
**`request_current_from_ammeter()` returns nothing**

*Location:* `Ammeters/client.py:4-12`

```python
def request_current_from_ammeter(port: int, command: bytes):
    with socket(AF_INET, SOCK_STREAM) as s:
        s.connect(('localhost', port))
        s.sendall(command)
        data = s.recv(1024)
        if data:
            print(f"Received current measurement from port {port}: {data.decode('utf-8')} A")
        else:
            print("No data received.")
```

The function prints the reading and implicitly returns `None`. The value is never parsed
into a `float` and never handed back, so the function cannot be used as a measurement API
— which is exactly what the whole framework needs to be built on.

*Required fix:* parse the reply to `float` and return it (inside a result object carrying
device, timestamp and success state, per Milestone 1). Printing becomes the caller's
choice, not a side effect.

*Verify:* `value = request_current_from_ammeter(...)` yields a usable number.

**☑ Fixed.** The function parses the reply and returns `float`; the prints were removed
rather than made conditional, since at sampling frequencies they would flood stdout and the
I/O itself perturbs the timing the framework exists to measure. The result object called for
above is `src/testing/measurement.py`'s frozen `Measurement` (device, current, unit, UTC
timestamp), built one layer up in `AmmeterTestFramework.get_measurement()` so the client
stays a thin transport. It carries no success flag — failures raise instead (ISS-12).

---

### ISS-05
**`Dict` is used but never imported**

*Location:* `src/testing/test_framework.py:10`

```python
def run_test(self, ammeter_type: str) -> Dict:
```

`Dict` is never imported. The annotation is evaluated when the class body executes, so
the module raises `NameError: name 'Dict' is not defined` **on import** — it cannot be
imported at all, which also breaks `examples/run_tests.py`.

*Required fix:* `from typing import Dict` (or use the built-in `dict` generic).

*Verify:* `python -c "import src.testing.test_framework"` succeeds from the repo root.

*Related:* the same file uses `from ..utils.config import load_config`, a relative import
that only resolves when imported as part of the package from the repo root — running the
file directly fails with "attempted relative import with no known parent package".
`run_test()` itself is an empty `pass`.

**☑ Fixed.** `from typing import Dict` added, and the relative import changed to the
absolute `from src.utils.config import load_config` — the file had been mixing both styles,
so it could only ever be imported one way.

The *Related* note — `run_test()` being an empty `pass` — was closed by section 4, which
made it the run entry point: it assigns the run ID, resolves the sampling configuration,
collects the samples and returns a `TestRunResult`.

---

### ISS-06
**`run_test()` called with no argument**

*Location:* `examples/run_tests.py:13`

```python
results[ammeter_type] = framework.run_test()      # signature: run_test(self, ammeter_type)
```

Raises `TypeError: run_test() missing 1 required positional argument: 'ammeter_type'` —
though the module fails earlier on ISS-05 anyway. The results loop below it prints a
header and no results.

*Required fix:* pass `ammeter_type`, and render the returned result.

---

### ISS-24
**`Ω` in a `print()` kills the Greenlee thread on a non-UTF-8 console**

*Location:* `Ammeters/Greenlee_Ammeter.py:15`

Found while verifying ISS-01 — not part of the original audit.

```python
print(f"Greenlee Ammeter - Voltage: {voltage}V, Resistance: {resistance}Ω, Current: {current}A")
```

`Ω` (U+03A9) cannot be encoded by most Windows ANSI code pages. On this machine
`sys.stdout.encoding` is `cp1255`, so the first measurement raises
`UnicodeEncodeError: 'charmap' codec can't encode character 'Ω'`. The exception
propagates out of `measure_current()` and out of the accept loop, killing the emulator
thread before `conn.sendall(...)` — so the client reports "No data received." and the
device is permanently dead for the rest of the process.

This masquerades as a protocol or port fault, which makes it especially expensive to
diagnose: with ISS-01 fixed, Greenlee was still the one device returning nothing while
ENTES and CIRCUTOR worked, because those two print only ASCII.

*Workaround for verification only:* `PYTHONIOENCODING=utf-8 python main.py`.

*Required fix:* stop writing non-ASCII to the console — route these through the logger
with an explicit UTF-8 encoding (ISS-09/ISS-22) and use `Ohm` in console text. Reconfiguring
`sys.stdout` would hide the class of bug rather than remove it, and a crash in a
measurement path should not depend on the operator's locale.

*Verify:* `python main.py` returns a Greenlee reading on a `cp1255`/`cp1252` console with
no environment override.

**☑ Fixed.** The console text reads `Resistance: {resistance} Ohm`; the inline comment on the
line above uses `Ohm` too, so a future edit does not reintroduce the character by copying it.
Verified as specified — `python main.py` on this machine's `cp1255` console, no
`PYTHONIOENCODING`, five Greenlee samples and all three devices in the comparison table.

Deliberately *not* done: reconfiguring `sys.stdout`, which would hide the class of bug rather
than remove it, and catching the exception in the accept loop, which would keep the thread
alive through a crash it should not be having — that error boundary belongs to ISS-18.

**Two related faults survive this fix.** The `print()` is still unconditional (ISS-22), and
the accept loop still has no error boundary (ISS-18), so *any* exception inside
`measure_current()` — not just this one — remains fatal to the device for the life of the
process. ISS-24 was one instance of that failure mode; it is the instance, not the mode, that
is now closed.

---

## 🟠 High

### ISS-07
**README documents the CIRCUTOR command without `-current`**

*Location:* `README.md:47` vs `Ammeters/Circutor_Ammeter.py:9`

README says `MEASURE_CIRCUTOR -get_measurement`; the emulator requires
`MEASURE_CIRCUTOR -get_measurement -current`. The README is wrong for this device — a
client written from the documentation is silently ignored.

*Required fix:* correct the README to match the code (or change both together, once
commands come from config).

**☑ Fixed.** `README.md:47` now documents `MEASURE_CIRCUTOR -get_measurement -current`,
matching `Circutor_Ammeter.py:9` and the config entry added under ISS-08. The emulator was
taken as the source of truth: it is the only one of the three that executes, and the flag
is what it actually compares against.

---

### ISS-08
**The entire `ammeters:` block in `config.yaml` is commented out**

*Location:* `config/config.yaml:7-16`

Every device entry is commented, so `load_config(...)['ammeters']` is `None`. The config
file currently carries no port or command information at all, which is why ports and
commands are duplicated (and contradicted) across `main.py` and the README.

*Required fix:* uncomment and populate, making this the single source of truth for
device name, port and command.

**☑ Fixed for the client side.** The block is uncommented and carries all three devices with
their `port` and `command`. `AmmeterTestFramework.get_measurement(ammeter_type)` resolves
both from it, so callers name a device instead of restating a port and a byte string, and
adding a fourth ammeter is a YAML edit rather than a code change.

**Not yet the single source of truth.** `main.py` still hardcodes the ports it *binds* when
constructing the emulators, so the server half of the duplication survives — config and code
can still drift, just in one place instead of three. Closing that means having the emulators
read the same registry, which lands with the lifecycle work in ISS-18.

---

### ISS-09
**The logger never attaches a handler — nothing is ever written**

*Location:* `src/utils/logger.py:10-26`

`_setup_logger` computes `log_dir` and `log_file`, creates the directory, then returns a
bare logger. No `FileHandler`, no `Formatter`, no level. Consequences:

- `log_file` is a dead variable; the log file is never created.
- No level is set, so the logger inherits `WARNING` — `info()` and `debug()` are discarded.
- With no handler, records fall through to the root logger's last-resort output.
- Two `TestLogger`s with the same `test_name` share one underlying logger and would stack
  handlers once handlers exist.

*Required fix:* attach a `FileHandler` (and optionally a `StreamHandler`) with a formatter,
set the level, and guard against duplicate handler registration.

*Verify:* after a run, `results/logs/<timestamp>_<test>.log` exists and is non-empty.

---

### ISS-10
**No `SO_REUSEADDR` — servers fail to restart**

*Location:* `Ammeters/base_ammeter.py:18-20`

`bind()` is called without `setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)`. After a run, the
listening socket sits in `TIME_WAIT` and the next start fails with
`OSError: [Errno 98] Address already in use`.

This is precisely the symptom the supplied comment in `main.py:31` hints at — *"if you
have problem restarting the servers between runs try increasing sleep time."* Sleeping
longer is a workaround for a one-line fix.

*Required fix:* set `SO_REUSEADDR` before `bind()`.

*Verify:* start, stop and immediately restart the emulators with no sleep and no error.

---

### ISS-11
**Unknown commands are dropped silently and the client hangs**

*Location:* `Ammeters/base_ammeter.py:27-30`

```python
if data == self.get_current_command:
    ...
    conn.sendall(str(current).encode('utf-8'))
```

There is no `else`. An unrecognised command produces no reply and no log line; the
connection simply closes. The client cannot distinguish "wrong command" from "device
broken" — and combined with ISS-12 (no timeout) this is what makes ISS-01 present as a
hang rather than an error.

*Required fix:* reply with an explicit error response and log the rejected command.

---

### ISS-12
**Client has no timeout and no error handling**

*Location:* `Ammeters/client.py:5-8`

No `settimeout()`, so a server that never replies blocks the caller indefinitely. No
handling for `ConnectionRefusedError` (server not up yet) or `OSError` (wrong port), and
no retry. During a sampling run, one unreachable device would stall the entire test.

*Required fix:* set an explicit timeout, catch connection errors, and surface them as a
failed-sample result so the run continues (Milestone 2).

**☑ Fixed.** `DEFAULT_TIMEOUT_SECONDS = 5.0` is applied via `settimeout()` before
`connect()`, so it covers the connect and the recv; it is a keyword argument, so a run can
lower it without touching the client. Failures now raise typed errors:

| Failure | Raised |
| --- | --- |
| Connect/socket failure, or timeout | `AmmeterConnectionError` |
| Reply empty, non-UTF-8, or non-numeric | `AmmeterResponseError` |

Two types rather than three: "unreachable" and "bad reply" call for different caller
behaviour, empty versus malformed does not.

**Note for anyone editing `client.py`:** `AmmeterError` derives from `RuntimeError` on
purpose. The response errors are raised *inside* the same `try` that guards the socket work,
so a base class of `OSError` or `ValueError` would have them caught by that handler and
silently relabelled as connection failures.

**Deviation from the required fix, deliberate.** Failures raise rather than returning a
failed-sample result. A result type that can also mean "no measurement" pushes the check onto
every consumer, and the one that forgets feeds `None` into `statistics.mean()` and fails far
from the cause. Run-level fault tolerance is still available and still Milestone 2's job: the
sampling loop catches `AmmeterError` per sample and keeps its own tally, which keeps the
"continue the run" behaviour without weakening the result type.

---

### ISS-13
**All sampling parameters are `NULL`**

*Location:* `config/config.yaml:2-5`

```yaml
sampling:
  measurements_count: NULL
  total_duration_seconds: NULL
  sampling_frequency_hz: NULL
```

No usable defaults, and no stated rule for which parameter wins when more than one is
supplied — count, duration and frequency are mutually constraining. `analysis.statistical_metrics`,
`analysis.visualization.plot_types` and `result_management:` are likewise empty keys that
parse to `None`.

*Required fix:* provide working defaults and define the precedence rule explicitly in
config and in the README.

**◐ Partially fixed.** The `sampling:` block now carries real defaults — `measurements_count: 5`,
`total_duration_seconds: 2`, `sampling_frequency_hz: 2` — and the rule is implemented and
documented: the three are over-determined, so any two derive the third and a contradictory
trio is rejected, which is stricter than the precedence rule this issue asked for and does not
silently discard whatever the operator wrote in the losing field.

**Still open:** the other half of this issue, the empty keys. `analysis.statistical_metrics`,
`analysis.visualization.plot_types` and `result_management:` all still parse to `None`, and
the analysis layer hardcodes its metric set rather than reading the first of them. This is the
gap the roadmap's Milestone 3 note refers to; it is tracked here rather than as a new ID
because it is the same defect the original audit recorded.

---

## 🟡 Medium

### ISS-14
**README describes files that do not exist**

*Location:* `README.md:7-24`

| README says | Reality |
| --- | --- |
| `Ammeters/main.py` | `main.py` is at the repo root |
| `examples/run_test.py` | file is `examples/run_tests.py` |
| `src/testing/AmmeterTester.py` | file is `src/testing/test_framework.py` |

The "Usage" heading is also empty and immediately followed by a duplicate
`# Ammeter Emulators` title.

*Required fix:* rewrite the structure section to match reality (Milestone 6).

---

### ISS-15
**Config file opened without an explicit encoding**

> **⏸ Deferred — nice to have.** `config/config.yaml` is pure ASCII, so the encoding bug is
> latent: it fires the day someone puts a non-ASCII device name in the registry. Accepting it
> also accepts ISS-19's remaining half, folded in here — `config_path` stays CWD-relative, so
> the framework runs only from the repo root. That is a usage constraint, not a silent
> failure, and it belongs in the README (ISS-14) instead of in code.

*Location:* `src/utils/config.py:8`

`open(config_path, 'r')` uses the platform default encoding — on Windows the ANSI code
page, not UTF-8 — so any non-ASCII content mis-decodes. The spec requires cross-platform
compatibility. There is also no file-not-found handling and no schema validation; an
empty file silently yields `None`.

*Required fix:* `open(config_path, 'r', encoding='utf-8')`, plus validation and a clear
error when the file is missing or malformed.

*Scope note (2026-08-18):* this issue also now owns resolving `AmmeterTestFramework`'s
`config_path` against the project root instead of the CWD, deferred here from ISS-19 so the
path, the missing-file error and the schema check land as one change. Validation should cover
a missing or `None` `ammeters:` section — `get_measurement` currently assumes it is a dict,
and an empty one raises `TypeError: argument of type 'NoneType' is not iterable`, which
points nowhere near the actual problem.

---

### ISS-16
**Global RNG reseeded per instance, producing correlated sequences**

*Location:* `Ammeters/base_ammeter.py:11`

```python
random.seed(time.time())   # in __init__, i.e. once per emulator instance
```

Two problems. First, this reseeds the **global** `random` module, so the last emulator
constructed dictates the sequence for every `random` call anywhere in the process.
Second, the three emulators are constructed back to back and `time.time()` has ~16 ms
resolution on Windows — they can land on the same seed and generate correlated
"measurements". For a QA framework whose entire purpose is measuring statistical
behaviour, correlated fake data undermines the results.

*Required fix:* give each emulator its own `random.Random(...)` instance seeded
independently.

---

### ISS-17
**Exact byte comparison against a single `recv()`**

> **⏸ Deferred — nice to have.** The commands are short, fixed, and sent in one `sendall`
> over loopback, where the kernel has never split one in practice. It is a real property of
> TCP rather than a bug that fires today, and it only becomes reachable if the protocol grows
> or leaves localhost. Pairs with ISS-20 — both are the same missing delimiter, seen from the
> two ends — so if either is ever done, both should be.

*Location:* `Ammeters/base_ammeter.py:26-27`

`data == self.get_current_command` compares raw bytes with no `.strip()`, so a trailing
newline fails the match. It also assumes the whole command arrives in one TCP segment —
TCP is a stream and may split it.

*Required fix:* read until a delimiter, then strip and compare normalised bytes.

---

### ISS-18
**Servers cannot be stopped, and serve one client at a time**

> **⏸ Deferred — nice to have, and the one deferral with a visible consequence.** The daemon
> threads do let the process exit cleanly, and sampling is sequential, so the queueing costs
> nothing at one client. What it blocks is elsewhere: the structural half of ISS-03 stays
> open, because removing `main.py`'s `sleep(5)` needs the readiness signal this issue would
> provide, and the Milestone 1 roadmap item *"emulator start/stop controllable from the
> framework"* cannot be ticked. The accept loop also still has no error boundary, so any
> exception inside `measure_current()` kills that device for the life of the process —
> ISS-24 was one instance of exactly that.

*Location:* `Ammeters/base_ammeter.py:22-30`

`while True:` with no shutdown mechanism — the servers cannot be stopped or joined, and
only exit because the threads are daemons. The accept loop also handles one connection at
a time, so concurrent sampling of a device queues.

*Required fix:* add a stop event and clean shutdown so the framework can manage emulator
lifecycle (Milestone 1).

*Also:* `bind(('localhost', ...))` can resolve to IPv6 `::1` on some systems while the
client resolves to IPv4 — bind explicitly to `127.0.0.1`.

---

### ISS-19
**No `__init__.py`; imports depend on the working directory**

> **⏸ Deferred — remaining half only.** The packaging half is done and stays done: all four
> directories are regular packages. What is deferred is the CWD-relative `config_path`, which
> was folded into ISS-15 so the path, the missing-file error and the schema check would land
> as one change. Deferring ISS-15 therefore defers this too.

*Location:* `Ammeters/`, `src/`, `src/utils/`, `src/testing/`

Imports work only via implicit namespace packages *and* only when the process starts from
the repo root. `python examples/run_tests.py` fails outright because the repo root is not
on `sys.path`. `AmmeterTestFramework`'s default `config_path="config/config.yaml"` is
likewise relative to the working directory.

*Required fix:* add `__init__.py` files and resolve the config path relative to the
project root rather than the CWD.

**◐ Partially fixed.** `__init__.py` was added to all four directories — `Ammeters/`, `src/`,
`src/testing/` and `src/utils/` — so they are regular packages. All four, not just the ones
currently imported: a regular package containing a namespace subpackage resolves on some
interpreters and layouts and not others, so a half-applied fix is worse than none.

**Still open:** `AmmeterTestFramework`'s default `config_path="config/config.yaml"` is
unchanged and remains relative to the working directory, so the framework still only works
when launched from the repo root. Resolving it against `__file__` was proposed and deferred
to ISS-15, so the path fix arrives together with the missing-file handling and schema
validation rather than leaving half a fix in two files. `python examples/run_tests.py` also
still fails on `sys.path` (ISS-06).

---

### ISS-20
**The wire protocol has no framing**

> **⏸ Deferred — nice to have.** The reply is a short float rendered as text, well under one
> segment, and the server closes the connection after it — which is the framing, implicitly.
> It holds on loopback and would not hold over a real network. Same missing delimiter as
> ISS-17; do them together or not at all, since changing one end alone breaks the protocol.

*Location:* `Ammeters/base_ammeter.py:30`, `Ammeters/client.py:8`

The server sends `str(current).encode('utf-8')` with no delimiter or length prefix, and
the client does a single `recv(1024)`. There is no way to know a message is complete.

*Required fix:* terminate messages with a newline and read until it.

---

### ISS-21
**Five heavy dependencies declared, one actually used**

*Location:* `requirements.txt`

`numpy`, `scipy`, `matplotlib`, `seaborn` and `pandas` are pinned, but only `pyyaml` is
imported anywhere in the supplied code. The spec's Technical Constraints say
*"minimize external library dependencies."*

*Required fix:* reduce to what is genuinely used, and justify every remaining entry in
`IMPLEMENTATION_NOTES.md`. Statistics can come from the standard library `statistics`
module.

---

### ISS-23
**The three devices produce non-comparable magnitudes**

*Location:* the three `measure_current()` implementations

| Device | Model | Approximate range |
| --- | --- | --- |
| Greenlee | I = V/R | 0.01 – 100 A |
| ENTES | I = B·K | 5 – 200 A |
| CIRCUTOR | I = Σ(V·Δt) | 0.005 – 0.05 A |

They are not measuring a shared physical current, and the ranges barely overlap. A naive
cross-device accuracy comparison — which the spec asks for as a bonus — would be
meaningless without normalisation or an explicitly stated reference.

CIRCUTOR's `sum(v * time_step)` is also a left-Riemann sum whose magnitude scales with
the randomly chosen `time_step`, injecting variance unrelated to the quantity supposedly
being measured.

*Not strictly a bug* — but it constrains the design of Milestone 5 and must be handled
explicitly rather than papered over.

*Resolved in Milestone 5.* Two ways, both explicit. Dispersion is normalised by dividing the
standard deviation by the mean, so the coefficient of variation is dimensionless and the
magnitude gap stops mattering. Accuracy is not reported at all, because no shared reference
current exists to report it against — and `compare_precision` states that in its output
rather than leaving a ranked table to imply otherwise. Section 3 had already closed the other
half by rejecting statistics over a mixed-device list. The CIRCUTOR Riemann-sum observation
stands: it is the reason CIRCUTOR shows the lowest variability of the three, since summing
ten terms averages the spread down by √10.

---

## ⚪ Low

### ISS-22
**Unconditional printing on every measurement**

> **⏸ Deferred — nice to have.** Noisy, and the write does sit inside the loop whose timing
> the framework measures, but it produces no wrong reading and no wrong statistic. The
> measured drift with the prints in place is 11 ms worst case at 2 Hz, well inside tolerance.
> Note that ISS-09 (the logger) *is* scheduled: once a working logger exists, converting
> these four `print()` calls to `logger.debug` is a few lines, so this is worth doing
> opportunistically on that branch rather than as work of its own.

*Location:* `Greenlee_Ammeter.py:15`, `Entes_Ammeter.py:15`, `Circutor_Ammeter.py:16,18`

Each `measure_current()` prints its internal values on every call. During high-frequency
sampling this floods stdout and interleaves with result output, and the I/O itself
perturbs the timing the framework is trying to measure precisely.

*Required fix:* route through the logger at debug level (see ISS-09).
