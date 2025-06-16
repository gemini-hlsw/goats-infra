import hashlib
import requests
from urllib.parse import urlparse


def get_latest_release_and_sha(repo_url: str) -> None:
    """Print the latest release tag and SHA256 for a GitHub repository.

    Parameters
    ----------
    repo_url : str
        The GitHub URL, e.g., https://github.com/gemini-hlsw/goats
    """
    # Extract owner and repo from URL.
    parsed = urlparse(repo_url)
    parts = parsed.path.strip("/").split("/")
    if len(parts) < 2:
        raise ValueError("Invalid GitHub URL format.")
    owner, repo = parts[:2]

    # Get latest release info.
    api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    response = requests.get(api_url, timeout=10)
    response.raise_for_status()
    data = response.json()
    tag = data["tag_name"].lstrip("v")

    # Download tarball and compute SHA256.
    tarball_url = f"https://github.com/{owner}/{repo}/archive/{tag}.tar.gz"
    tarball = requests.get(tarball_url, timeout=20)
    tarball.raise_for_status()
    sha256 = hashlib.sha256(tarball.content).hexdigest()

    print(f"Release: {tag}")
    print(f"SHA256: {sha256}")


if __name__ == "__main__":
    get_latest_release_and_sha("https://github.com/gemini-hlsw/goats")
