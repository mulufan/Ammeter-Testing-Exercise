"""Remove build artefacts: caches, coverage output, run logs.

`git clean -Xdf` is the usual one-liner, but `.gitignore` here also covers `.venv/` and
the assignment PDF, so the targets are listed explicitly instead. `results/samples/` holds
the committed sample runs and is deliberately absent from the list.

    python scripts/clean.py -n        # list what would go
    python scripts/clean.py           # caches, coverage output, run logs
    python scripts/clean.py --runs    # also the run archive under results/runs/
"""

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = {".git", ".venv", "venv"}

DEFAULT_PATTERNS = [
    "**/__pycache__", "**/*.py[co]", ".pytest_cache",
    ".coverage", ".coverage.*", "coverage.xml", "htmlcov",
    "results/logs/*",
]
RUNS_PATTERN = "results/runs/*"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", action="store_true",
                        help="also clear results/runs/ (local run history, not build output)")
    parser.add_argument("-n", "--dry-run", action="store_true",
                        help="list what would be removed, delete nothing")
    args = parser.parse_args(argv)

    patterns = DEFAULT_PATTERNS + ([RUNS_PATTERN] if args.runs else [])
    matched = {path for pattern in patterns for path in ROOT.glob(pattern)
               if SKIP.isdisjoint(path.parts)}
    # Drop what a parent already covers: a .pyc inside a __pycache__ that is going too.
    targets = sorted(path for path in matched if matched.isdisjoint(path.parents))

    for path in targets:
        print(f"{'would remove' if args.dry_run else 'removed'} {path.relative_to(ROOT)}")
        if not args.dry_run:
            shutil.rmtree(path) if path.is_dir() else path.unlink()

    print(f"\n{len(targets)} item(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
