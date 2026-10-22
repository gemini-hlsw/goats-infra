"""Delete pre-release channel packages nobody needs any more, so it stays small.

Used for conda-test and conda-dev. Keeps:

- the newest ``--keep`` GOATS versions;
- any final GOATS version not yet promoted to conda;
- in conda-dev, only the gpp-client .devN those GOATS pin: one is built when
  a dev GOATS first pins it and goes away with the last GOATS that does;
- every other package (the jdaviz stack): it is small and GOATS needs it.

Run with a Python that has conda installed, then reindex the channel.
"""

import argparse
import json
import logging
import re
from pathlib import Path

from conda.models.version import VersionOrder

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

SUBDIRS = ("noarch", "linux-64", "osx-64")
FINAL_VERSION = re.compile(r"^\d+(\.\d+)*(\.post\d+)?$")


def load_records(channel: Path) -> list[dict]:
    """Return every package file in a channel directory, read from its repodata."""
    records = []
    for subdir in SUBDIRS:
        path = channel / subdir / "repodata.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        for key in ("packages", "packages.conda"):
            for fn, record in data.get(key, {}).items():
                if (channel / subdir / fn).exists():
                    records.append({**record, "subdir": subdir, "fn": fn})
    return records


def newest_versions(records: list[dict], count: int) -> set[str]:
    versions = {r["version"] for r in records}
    return set(sorted(versions, key=VersionOrder, reverse=True)[:count])


def pinned_gpp_client(record: dict) -> str | None:
    for dep in record.get("depends", []):
        match = re.fullmatch(r"gpp-client\s*==\s*(\S+)", dep)
        if match:
            return match.group(1)
    return None


def plan(records: list[dict], prod: list[dict], keep: int) -> list[dict]:
    """Return the channel records to delete."""
    goats = [r for r in records if r["name"] == "goats"]
    promoted = {r["version"] for r in prod if r["name"] == "goats"}
    keep_goats = newest_versions(goats, keep) | {
        r["version"]
        for r in goats
        if FINAL_VERSION.match(r["version"]) and r["version"] not in promoted
    }
    keep_gpp = {pinned_gpp_client(r) for r in goats if r["version"] in keep_goats}
    return [
        r
        for r in records
        if (r["name"] == "goats" and r["version"] not in keep_goats)
        or (r["name"] == "gpp-client" and r["version"] not in keep_gpp)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("channel", type=Path, help="conda-test or conda-dev channel directory")
    parser.add_argument(
        "--prod",
        type=Path,
        default=Path("docs/gh_pages/conda"),
        help="Production channel directory (default: %(default)s)",
    )
    parser.add_argument("--keep", type=int, default=3)
    parser.add_argument("--dry-run", "-n", action="store_true")
    args = parser.parse_args()

    doomed = plan(load_records(args.channel), load_records(args.prod), args.keep)
    for record in sorted(doomed, key=lambda r: (r["subdir"], r["fn"])):
        logger.info("  - %s/%s", record["subdir"], record["fn"])
        if not args.dry_run:
            (args.channel / record["subdir"] / record["fn"]).unlink()
    logger.info("%d package file(s) %s.", len(doomed), "to delete" if args.dry_run else "deleted")


if __name__ == "__main__":
    main()
