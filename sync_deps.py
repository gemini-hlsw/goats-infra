import argparse
import logging
import re
from pathlib import Path

import tomllib

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Dependencies declared in pyproject that must NOT be synced into the conda
# recipe because they are not available on any conda channel. They are installed
# via pip instead (e.g. by `goats install`). Names must be normalized.
CONDA_EXCLUDED = {"jdaviz"}


def normalize(name: str) -> str:
    return re.sub(r"[-\.]", "_", name).lower()


def parse_dependency(dep: str) -> tuple[str, str] | None:
    # Strip extras like [daphne] or [redis,watch] before parsing.
    dep_clean = re.sub(r"\[.*?\]", "", dep.strip())
    match = re.match(r"^([A-Za-z0-9_\-\.]+)\s*([><=!].*)?$", dep_clean)
    if not match:
        return None
    name = normalize(match.group(1))
    constraint = (match.group(2) or "").strip()
    return name, constraint


def load_dependencies(pyproject_path: Path) -> dict[str, str]:
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)

    deps = data.get("project", {}).get("dependencies", [])
    result = {}
    for dep in deps:
        parsed = parse_dependency(dep)
        if parsed:
            name, constraint = parsed
            if name in CONDA_EXCLUDED:
                logger.info("  skipping (not on conda, installed via pip): %s", name)
                continue
            result[name] = constraint
        else:
            logger.warning("  could not parse: %s", dep)
    return result


def load_uv_sources(pyproject_path: Path) -> dict[str, str]:
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)

    sources = data.get("tool", {}).get("uv", {}).get("sources", {})
    result = {}
    for package, source in sources.items():
        tag = source.get("tag")
        if tag:
            name = normalize(package)
            result[name] = f"=={tag.lstrip('v')}"
    return result


def extract_current_constraint(content: str, package: str) -> str:
    """Extract the current version constraint for a package in meta.yaml."""
    flexible_name = re.sub(r"_", r"[-_]", re.escape(package))
    pattern = rf"[ \t]*-[ \t]+{flexible_name}(?![-_a-zA-Z0-9])([ \t]*[><=!][^\n]*)?"
    match = re.search(pattern, content, flags=re.IGNORECASE)
    if match:
        return (match.group(1) or "").strip()
    return ""


def update_meta_yaml(
    content: str, dependencies: dict[str, str], uv_packages: set[str]
) -> tuple[str, list[tuple], list[tuple]]:
    updated = content
    changed = []  # list of (package, old_constraint, new_constraint)
    added = []  # list of (package, new_constraint)

    for package, constraint in dependencies.items():
        flexible_name = re.sub(r"_", r"[-_]", re.escape(package))
        pattern = (
            rf"([ \t]*-[ \t]+{flexible_name})(?![-_a-zA-Z0-9])([ \t]*[><=!][^\n]*)?"
        )
        replacement = rf"\g<1> {constraint}" if constraint else rf"\g<1>"

        new_content, count = re.subn(pattern, replacement, updated, flags=re.IGNORECASE)
        if count > 0:
            old_constraint = extract_current_constraint(updated, package)
            if old_constraint != constraint:
                changed.append((package, old_constraint, constraint))
            updated = new_content
        else:
            # If it comes from uv.sources (git-pinned) and is not in meta.yaml, skip it.
            if package in uv_packages:
                continue
            # Otherwise append it under the run: section.
            new_entry = f"    - {package} {constraint}".rstrip()
            run_pattern = r"([ \t]*run:[ \t]*\n(?:[ \t]*-[^\n]*\n)*)"
            updated = re.sub(run_pattern, rf"\1{new_entry}\n", updated, count=1)
            added.append((package, constraint))

    return updated, changed, added


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync dependencies from pyproject.toml into conda recipe meta.yaml."
    )
    parser.add_argument("--pyproject-path", type=Path, default=Path("./pyproject.toml"))
    parser.add_argument("--meta-path", type=Path, default=Path("./recipe/meta.yaml"))
    parser.add_argument("--dry-run", "-n", action="store_true")
    args = parser.parse_args()

    deps = load_dependencies(args.pyproject_path)
    uv = load_uv_sources(args.pyproject_path)
    deps.update(uv)

    content = args.meta_path.read_text()
    updated_content, changed, added = update_meta_yaml(content, deps, set(uv.keys()))

    if not changed and not added:
        logger.info("meta.yaml already up to date.")
        return

    if args.dry_run:
        if changed:
            logger.info("Dry-run — would update:")
            for pkg, old, new in changed:
                logger.info("  ~ %s: %s -> %s", pkg, old or "(none)", new)
        if added:
            logger.info("Dry-run — would add:")
            for pkg, new in added:
                logger.info("  + %s %s", pkg, new)
        return

    args.meta_path.write_text(updated_content)
    if changed:
        logger.info("Updated %d package(s):", len(changed))
        for pkg, old, new in changed:
            logger.info("  ~ %s: %s -> %s", pkg, old or "(none)", new)
    if added:
        logger.info("Added %d package(s):", len(added))
        for pkg, new in added:
            logger.info("  + %s %s", pkg, new)


if __name__ == "__main__":
    main()
