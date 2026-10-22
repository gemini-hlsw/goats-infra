"""Copy a final release from conda-test to conda, with the conda-test packages it needs.

Only already-built files are copied, so production gets the exact bytes that
were tested. A dependency is copied when conda-test carries it (it is one of
ours, e.g. jdaviz) and nothing in conda satisfies the dependency yet.
gpp-client is never copied: production gets it from conda-forge.

Run from the repository root with a Python that has conda installed, then
reindex the target channel.
"""

import argparse
import json
import logging
import re
import shutil
import sys
from pathlib import Path

from conda.models.match_spec import MatchSpec
from conda.models.version import VersionOrder

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

SUBDIRS = ("noarch", "linux-64", "osx-64")
FINAL_VERSION = re.compile(r"^\d+(\.\d+)*(\.post\d+)?$")
# Packages production always takes from conda-forge, never from our channels.
FROM_CONDA_FORGE = {"gpp-client"}


def load_channel(channel: Path) -> list[dict]:
    """Return every package record in a channel directory, tagged with subdir and fn."""
    records = []
    for subdir in SUBDIRS:
        path = channel / subdir / "repodata.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        for key in ("packages", "packages.conda"):
            for fn, record in data.get(key, {}).items():
                records.append({**record, "subdir": subdir, "fn": fn})
    return records


def compatible(record: dict, subdir: str) -> bool:
    return record["subdir"] in ("noarch", subdir)


def newest(records: list[dict]) -> dict:
    return max(records, key=lambda r: (VersionOrder(r["version"]), r["build_number"]))


def plan(package: str, version: str, test: list[dict], prod: list[dict]) -> list[dict]:
    """Return the conda-test records to copy, the requested ones first."""
    targets = [r for r in test if r["name"] == package and r["version"] == version]
    if not targets:
        sys.exit(f"No {package}-{version} in conda-test. Build and publish it there first.")

    hosted = {r["name"] for r in test} - FROM_CONDA_FORGE
    chosen = list(targets)
    queue = list(targets)
    while queue:
        record = queue.pop()
        for dep in record.get("depends", []):
            spec = MatchSpec(dep)
            if spec.name not in hosted:
                continue
            available = [r for r in prod + chosen if compatible(r, record["subdir"])]
            if any(spec.match(r) for r in available):
                continue
            candidates = [
                r for r in test if compatible(r, record["subdir"]) and spec.match(r)
            ]
            if not candidates:
                sys.exit(f"{record['fn']} needs {dep}, which conda-test does not carry.")
            pick = newest(candidates)
            logger.info("  %s needs %s -> %s", record["fn"], dep, pick["fn"])
            chosen.append(pick)
            queue.append(pick)
    return chosen


def check_final_versions(records: list[dict]) -> None:
    # Users only get final releases: no rcN, devN, aN or bN, ours or upstream's.
    for record in records:
        if not FINAL_VERSION.match(record["version"]):
            sys.exit(f"{record['fn']} is a pre-release; only final versions reach conda.")


def check_dev_pins(records: list[dict]) -> None:
    # A GOATS pinned to a gpp-client .devN talks to GPP development.
    for record in records:
        for dep in record.get("depends", []):
            spec = MatchSpec(dep)
            if spec.name == "gpp-client" and ".dev" in str(spec.version):
                sys.exit(f"{record['fn']} pins {dep}; only stable gpp-client reaches conda.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("package")
    parser.add_argument("version")
    parser.add_argument("--source", type=Path, required=True, help="conda-test channel directory")
    parser.add_argument(
        "--target",
        type=Path,
        default=Path("docs/gh_pages/conda"),
        help="Production channel directory (default: %(default)s)",
    )
    parser.add_argument("--dry-run", "-n", action="store_true")
    args = parser.parse_args()

    # gpp-client in conda would hide every conda-forge release (strict priority).
    if args.package in FROM_CONDA_FORGE:
        sys.exit(f"{args.package} is never promoted: production gets it from conda-forge.")

    chosen = plan(args.package, args.version, load_channel(args.source), load_channel(args.target))
    check_final_versions(chosen)
    check_dev_pins(chosen)

    for record in chosen:
        src = args.source / record["subdir"] / record["fn"]
        dst = args.target / record["subdir"] / record["fn"]
        print(record["fn"])
        if not args.dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


if __name__ == "__main__":
    main()
