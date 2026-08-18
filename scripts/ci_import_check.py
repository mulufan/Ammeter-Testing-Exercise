"""Import every Python module in the project and report the ones that fail.

Byte-compiling (``python -m compileall``) only proves the sources parse. Importing
them additionally executes module level code, which is what catches missing imports,
bad relative imports and broken package layout - the kind of defect catalogued in
ISSUES.md.

Modules are imported, not executed: every entry point in this repository guards its
work behind ``if __name__ == "__main__":``, so nothing binds a socket here.

Run locally before pushing:

    python scripts/ci_import_check.py
"""

import importlib
import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Directories scanned for modules, plus any top level scripts worth importing.
PACKAGE_DIRS = ("Ammeters", "src", "examples")
TOP_LEVEL_MODULES = ("main",)

# Directories that never contain project sources.
SKIP_DIRS = {"__pycache__", ".venv", "venv", ".git", ".idea", "build", "dist"}


def discover_modules():
    """Return the dotted module names to import, in a stable order."""
    modules = []

    for name in TOP_LEVEL_MODULES:
        if (REPO_ROOT / f"{name}.py").is_file():
            modules.append(name)

    for package_dir in PACKAGE_DIRS:
        root = REPO_ROOT / package_dir
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            if any(part in SKIP_DIRS for part in path.relative_to(REPO_ROOT).parts):
                continue
            relative = path.relative_to(REPO_ROOT).with_suffix("")
            parts = list(relative.parts)
            if parts[-1] == "__init__":
                parts.pop()
            if parts:
                modules.append(".".join(parts))

    return modules


def main():
    # Imports such as ``from src.utils.config import load_config`` resolve relative to
    # the repository root, so make sure it is on the path regardless of the caller's
    # working directory.
    sys.path.insert(0, str(REPO_ROOT))

    failures = []
    for module in discover_modules():
        try:
            importlib.import_module(module)
        except Exception:
            failures.append(module)
            print(f"FAIL {module}", flush=True)
            traceback.print_exc()
        else:
            print(f"OK   {module}", flush=True)

    print(f"\n{len(failures)} module(s) failed to import.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
