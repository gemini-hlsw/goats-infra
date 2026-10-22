"""Run ``pip check`` and fail on any broken requirement except known ones.

Each entry in ``KNOWN_ISSUES`` is an upstream packaging bug we cannot fix
here. Remove an entry as soon as the upstream fix is published; the script
warns when an entry no longer matches anything.

A copy lives in ``dependency-feedstocks/recipes/jdaviz/``; keep both in sync.
"""

import subprocess
import sys

KNOWN_ISSUES = (
    # conda-forge glue-jupyter 0.29.0 (pyhd8ed1ab_0) installs its metadata as
    # version 0.0.0, so jdaviz's "glue-jupyter>=0.27.0" looks unmet.
    "but you have glue-jupyter 0.0.0",
)

result = subprocess.run(
    [sys.executable, "-m", "pip", "check"], capture_output=True, text=True
)
print(result.stdout + result.stderr)

lines = [
    line
    for line in result.stdout.splitlines()
    if line.strip() and not line.startswith("No broken requirements")
]
problems = [line for line in lines if not any(issue in line for issue in KNOWN_ISSUES)]

for issue in KNOWN_ISSUES:
    if not any(issue in line for line in lines):
        print(f"WARNING: known issue no longer reported, remove it: {issue!r}")

if problems:
    print("Unexpected pip check failures:", *problems, sep="\n  ")
    sys.exit(1)
