import argparse
import hashlib
import logging
import re
from pathlib import Path
from urllib.parse import urlparse

import requests

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def get_latest_release_and_sha(repo_url: str) -> tuple[str, str]:
    """
    Get the latest release tag and SHA256 for a GitHub repository.

    Parameters
    ----------
    repo_url : str
        The URL of the GitHub repository.

    Returns
    -------
    tuple[str, str]
        A tuple containing the latest release tag and its SHA256 hash.
    """
    logger.info(f"Fetching latest release info from {repo_url}")
    # Extract owner and repo from URL.
    parsed = urlparse(repo_url)
    parts = parsed.path.strip("/").split("/")
    if len(parts) < 2:
        logger.exception("Invalid GitHub URL format.")
        raise ValueError("Invalid GitHub URL format.")
    owner, repo = parts[:2]

    # Get latest release info.
    api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    response = requests.get(api_url, timeout=10)
    response.raise_for_status()
    data = response.json()
    tag = data["tag_name"].lstrip("v")
    logger.info("Latest release tag: %s ", tag)

    # Download tarball and compute SHA256.
    tarball_url = f"https://github.com/{owner}/{repo}/archive/{tag}.tar.gz"
    tarball = requests.get(tarball_url, timeout=20)
    tarball.raise_for_status()
    sha256 = hashlib.sha256(tarball.content).hexdigest()
    logger.info("Computed SHA256: %s", sha256)

    return tag, sha256


def update_meta_yaml(meta_path: Path, version: str, sha256: str) -> bool:
    """
    Update the meta.yaml file with the new version and SHA256.

    Parameters
    ----------
    meta_path : Path
        The path to the meta.yaml file.
    version : str
        The new version to set.
    sha256 : str
        The new SHA256 to set.

    Returns
    -------
    bool
        ``True`` if the file was updated, ``False`` if no changes were needed.
    """
    content = meta_path.read_text()

    version_pattern = r'{%\s*set version\s*=\s*"([^"]+)"\s*%}'
    sha256_pattern = r"sha256:\s*([a-f0-9]{0,64})"

    current_version_match = re.search(version_pattern, content)
    current_sha_match = re.search(sha256_pattern, content, re.IGNORECASE)

    if not current_version_match or not current_sha_match:
        logger.exception("Could not find version or sha256 in meta.yaml.")
        raise ValueError("Could not find version or sha256 in meta.yaml.")

    current_version = current_version_match.group(1)
    current_sha = current_sha_match.group(1)
    logger.info("Current version: %s, Current SHA256: %s", current_version, current_sha)
    logger.info("New version: %s, New SHA256: %s", version, sha256)

    if current_version == version and current_sha == sha256:
        logger.info("meta.yaml is already up to date.")
        return False

    # Replace version and sha256.
    updated = re.sub(
        version_pattern,
        f'{{% set version = "{version}" %}}',
        content,
    )
    updated = re.sub(sha256_pattern, f"sha256: {sha256}", updated, flags=re.IGNORECASE)

    meta_path.write_text(updated)
    logger.info("Updated meta.yaml to version=%s and sha256=%s", version, sha256)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update conda recipe meta.yaml with latest GitHub release version and SHA256."
    )
    parser.add_argument(
        "--repo-url",
        default="https://github.com/gemini-hlsw/goats",
        help="GitHub repository URL (default: %(default)s)",
    )
    parser.add_argument(
        "--meta-path",
        type=Path,
        default=Path("./goats-feedstock/recipe/meta.yaml"),
        help="Path to meta.yaml file (default: %(default)s)",
    )
    parser.add_argument(
        "--print-only",
        "-p",
        action="store_true",
        help="Only print the latest version and SHA256 without modifying meta.yaml",
    )

    args = parser.parse_args()

    version, sha256 = get_latest_release_and_sha(args.repo_url)

    if args.print_only:
        return
    else:
        logger.info("Starting update of meta.yaml.")
        update_meta_yaml(args.meta_path, version, sha256)
        logger.info("Update process complete.")


if __name__ == "__main__":
    main()
