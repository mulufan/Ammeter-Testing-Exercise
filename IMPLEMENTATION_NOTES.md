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

*Resolved 2026-08-18 — the README was corrected to match the emulator.*

---

## 2026-08-18 — Unified measurement API

Branch: `feature/unified-measurement-api`. One entry point for all three devices, driven by
the config registry, returning one result type and raising on failure. Sampling, statistics,
storage and logging are out of scope.

Closes ISS-04, ISS-07, ISS-08 and ISS-12, plus the import half of ISS-05 and ISS-19.

### Fixes

- **ISS-08** — `ammeters:` uncommented and populated. `config.yaml` is now the registry that
  `get_measurement()` reads port and command from, so adding a device is a YAML edit. `main.py`
  still hardcodes the ports it *binds*, so the server half of the duplication remains (ISS-18).
- **ISS-04 / ISS-12** — the client returns `float` instead of printing and returning `None`;
  applies `settimeout(5.0)` before `connect()`, covering both connect and recv; and raises
  `AmmeterConnectionError` (unreachable or timed out) or `AmmeterResponseError` (empty,
  non-UTF-8, or non-numeric reply) instead of hanging or surfacing a bare `OSError`.
- **ISS-05 / ISS-19** — `Dict` imported; the relative `..utils.config` import made absolute to
  match the rest of the file; `__init__.py` added to all four package directories. Adding only
  some is worse than none — a regular package containing a namespace subpackage resolves on
  some interpreters and not others.
- **ISS-07** — README CIRCUTOR command corrected to `-get_measurement -current`. The emulator
  is the source of truth; the README was wrong.

### Decisions

- **`Measurement` dataclass, not a `Dict`.** Typed fields catch a mistyped key at the point of
  the mistake rather than as a `None` several stages later, and `dataclasses.asdict()` covers
  the storage stage. Frozen, because a sample records something that already happened.
- **Timestamp is a timezone-aware UTC `datetime`.** Comparable without parsing, so the sampling
  engine can measure actual versus requested intervals; formatting belongs at the storage
  boundary. Naive local times break comparison across machines and across a DST change.
- **No `ok` / `error` fields — failures raise.** A result type that can mean "no measurement"
  pushes the check onto every consumer, and the one that forgets feeds `None` into
  `statistics.mean()`. The cost lands in the sampling stage: a fault-tolerant run must catch
  `AmmeterError` per sample and keep its own tally of failures.
- **Two exception types, not three.** "Unreachable" and "bad reply" call for different caller
  behaviour; empty versus malformed does not.
- **`AmmeterError` derives from `RuntimeError` deliberately.** Response errors are raised
  inside the same `try` that guards the socket, so a base of `OSError` or `ValueError` would
  see them caught by that handler and relabelled as connection failures. Do not change this
  base class without re-reading this line.

### Dependencies

None added. `dataclasses`, `datetime`, `socket` and `typing` are all standard library.

### Verification

`python main.py` — one `Measurement` per device (emulator debug prints omitted):

```
Measurement(ammeter_type='greenlee', current=0.1452933538316761, unit='A', timestamp=datetime.datetime(2026, 8, 18, 11, 40, 49, 148726, tzinfo=datetime.timezone.utc))
Measurement(ammeter_type='entes',    current=11.536727984656562,  unit='A', timestamp=...164440, tzinfo=datetime.timezone.utc))
Measurement(ammeter_type='circutor', current=0.04114656601847207, unit='A', timestamp=...181479, tzinfo=datetime.timezone.utc))
```

Error paths, via an ad-hoc probe (not committed) running a real emulator alongside two
stand-in servers replying with deliberate junk:

```
[dead port]                    AmmeterConnectionError: ... on port 5999: timed out
[wrong command (empty reply)]  AmmeterResponseError:   No response received from ammeter on port 5001
[non-numeric reply]            AmmeterResponseError:   Invalid response received from ammeter on port 5901
[non-utf8 reply]               AmmeterResponseError:   Invalid response received from ammeter on port 5902
```

The dead-port case reports `timed out` because Windows drops a connect to a closed loopback
port rather than refusing it; Linux reports `Connection refused`. Both classify correctly.

**ISS-24 is not fixed** — it merely did not trigger, because `sys.stdout.encoding` was `utf-8`
in the shell used here.

### Files touched

| File | Change |
| --- | --- |
| `Ammeters/client.py` | Returns `float`; timeout; exception hierarchy; prints removed (ISS-04, ISS-12). |
| `src/testing/measurement.py` | **New.** Frozen `Measurement` dataclass with UTC timestamp. |
| `src/testing/test_framework.py` | `get_measurement()` resolves port/command from config and returns a `Measurement`; imports fixed (ISS-05). |
| `config/config.yaml` | `ammeters:` block uncommented and populated (ISS-08). |
| `README.md` | CIRCUTOR command corrected (ISS-07). |
| `Ammeters/`, `src/`, `src/testing/`, `src/utils/` — `__init__.py` | **New**, empty (ISS-19, partial). |
| `main.py` | Calls the framework per device and prints the result. |

### Still open

- `config_path` is still CWD-relative and the config is unvalidated — deferred to ISS-15 so the
  path fix and the missing-file/schema handling land together rather than half in two places.
- `main.py` keeps the supplied `sleep(5)` and trailing `pass`; removing them needs ISS-10 and a
  readiness signal (ISS-18), not just deletion.
- `AmmeterResponseError` names the port but not the offending payload — recoverable from the
  chained traceback, absent from the log line an operator actually reads.
