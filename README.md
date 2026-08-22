# Ammeter Emulators

This project provides emulators for different types of ammeters: Greenlee, ENTES, and CIRCUTOR. Each ammeter emulator runs on a separate thread and can respond to current measurement requests.

## Project Structure

- `Ammeters/`
  - `main.py`: Main script to start the ammeter emulators and request current measurements.
  - `Circutor_Ammeter.py`: Emulator for the CIRCUTOR ammeter.
  - `Entes_Ammeter.py`: Emulator for the ENTES ammeter.
  - `Greenlee_Ammeter.py`: Emulator for the Greenlee ammeter.
  - `base_ammeter.py`: Base class for all ammeter emulators.
  - `client.py`: Client to request current measurements from the ammeter emulators.
- `config/`
  - `config.yaml`: Configuration file for the ammeter emulators.
- `examples/`
  - `run_test.py`: super lyze example for run test **don't use it**.
- `src/`
  - `testing/`
    - `AmmeterTester.py`: Class to test the ammeter emulators.
  - `utils/`
    - `config.py`: Configuration settings.
    - `logger.py`: Logging setup.
    - `Utils.py`: Utility functions, including `generate_random_float`.

## Usage

# Ammeter Emulators

## Greenlee Ammeter

- **Port**: 5001
- **Command**: `MEASURE_GREENLEE -get_measurement`
- **Measurement Logic**: Calculates current using voltage (1V - 10V) and (0.1Ω - 100Ω).
- **Measurement method** : Ohm's Law: I = V / R

## ENTES Ammeter

- **Port**: 5002
- **Command**: `MEASURE_ENTES -get_data`
- **Measurement Logic**: Calculates current using magnetic field strength (0.01T - 0.1T) and calibration factor (500 - 2000).
- **Measurement method** : Hall Effect: I = B * K

## CIRCUTOR Ammeter

- **Port**: 5003
- **Command**: `MEASURE_CIRCUTOR -get_measurement -current`
- **Measurement Logic**: Calculates current using voltage values (0.1V - 1.0V) over a number of samples and a random time step (0.001s - 0.01s).
- **Measurement method** : Rogowski Coil Integration: I = ∫V dt

## Requirements

**Python 3.10 or newer.** The framework uses built-in generic types (`list[Measurement]`)
and `X | None` annotations, both of which are evaluated at import time.

Install the dependencies first. The framework is standard library only apart from
`pyyaml` (reads `config/config.yaml`) and `matplotlib` (draws the per-run plot below):

```sh
pip install -r requirements.txt
```

To start the ammeter emulators and request current measurements, run the `main.py` script:
```sh
python main.py
```

## Run Output

Each completed run is written to `results/runs/` under its own UUID test ID:

| File | Contents |
| --- | --- |
| `<test_id>.json` | the whole run — sampling configuration, every raw sample, and the statistics |
| `<test_id>.png` | a line plot of measured current (A) against the timestamp of each sample |
| `results/logs/<device>_<id>.log` | that run's log, from first sample to final statistics |

The plot is deliberately minimal: one line with point markers, titled with the ammeter type
and the short run ID, labelled axes and a grid. It is drawn by
`plot_measurement_series(result)` in `src/testing/visualization.py`, which can also be called
on any `TestRunResult` directly:

```python
from src.testing.visualization import plot_measurement_series

path = plot_measurement_series(result)   # results/runs/<test_id>.png
```

It renders through Matplotlib's `Agg` backend, so it writes files without needing a display,
and raises `ValueError` for a run that collected no measurements.

## Development Workflow

`master` is protected by convention: nothing is committed to it directly. All work
follows the same path.

1. **Branch** off `master` — `feature/<desc>`, `fix/<desc>`, `chore/<desc>`,
   `refactor/<desc>` or `test/<desc>` (lowercase with hyphens).
2. **Commit and push** the branch.
3. **Open a pull request** targeting `master`.
4. **CI must pass.** [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on every
   pull request against `master`: it sets up Python, installs `requirements.txt`,
   byte-compiles every source file, and imports every module.
5. **Merge to `master`** once CI is green and the change has been reviewed.
6. **Delete the branch** in both places — remote and local (`git branch -d <branch>`).

### Running the CI checks locally

The same two checks CI runs, before you push:

```sh
python -m compileall -q main.py Ammeters src examples scripts
python scripts/ci_import_check.py
```

Both checks now block a merge. The import check was reported without enforcing while
`master` still carried the ISS-05 import failure (`src/testing/test_framework.py`, see
[`ISSUES.md`](ISSUES.md)); that fix has landed, so `continue-on-error` is gone. Tests are
not part of CI yet; when `pytest` arrives it is added as one more step after the import
check.
