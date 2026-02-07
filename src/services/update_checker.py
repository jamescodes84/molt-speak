"""
Update Checker for Molt-Speak

Checks GitHub for new releases and prompts users to update.
"""

import json
import logging
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Tuple
from packaging import version

logger = logging.getLogger(__name__)


class UpdateChecker:
    """Check for application updates from GitHub."""

    def __init__(
        self,
        repo_owner: str = "jamescodes84",
        repo_name: str = "molt-speak",
        current_version: Optional[str] = None
    ):
        """
        Initialize update checker.

        Args:
            repo_owner: GitHub username
            repo_name: GitHub repository name
            current_version: Current app version (reads from VERSION file if not provided)
        """
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.github_api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"

        # Get current version
        if current_version:
            self.current_version = current_version
        else:
            self.current_version = self._read_version_file()

        logger.info(f"Update checker initialized. Current version: {self.current_version}")

    def _read_version_file(self) -> str:
        """Read version from VERSION file."""
        try:
            version_file = Path(__file__).parent.parent.parent / "VERSION"
            if version_file.exists():
                return version_file.read_text().strip()
            else:
                logger.warning("VERSION file not found, using default 1.0.0")
                return "1.0.0"
        except Exception as e:
            logger.error(f"Failed to read VERSION file: {e}")
            return "1.0.0"

    def check_for_updates(self, timeout: int = 5) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Check GitHub for new releases.

        Args:
            timeout: Request timeout in seconds

        Returns:
            Tuple of (update_available, latest_version, download_url)
        """
        try:
            # Create request with timeout
            req = urllib.request.Request(
                self.github_api_url,
                headers={'User-Agent': 'Molt-Speak-Update-Checker'}
            )

            # Fetch latest release info
            with urllib.request.urlopen(req, timeout=timeout) as response:
                data = json.loads(response.read().decode())

            latest_version = data.get("tag_name", "").lstrip("v")
            download_url = data.get("html_url")

            if not latest_version:
                logger.warning("No version tag found in latest release")
                return False, None, None

            # Compare versions
            try:
                current = version.parse(self.current_version)
                latest = version.parse(latest_version)

                if latest > current:
                    logger.info(f"Update available: {self.current_version} → {latest_version}")
                    return True, latest_version, download_url
                else:
                    logger.info(f"Already on latest version: {self.current_version}")
                    return False, latest_version, download_url

            except version.InvalidVersion as e:
                logger.error(f"Invalid version format: {e}")
                return False, None, None

        except urllib.error.HTTPError as e:
            if e.code == 404:
                logger.warning("No releases found on GitHub")
            else:
                logger.error(f"HTTP error checking for updates: {e.code} {e.reason}")
            return False, None, None

        except urllib.error.URLError as e:
            logger.warning(f"Network error checking for updates: {e.reason}")
            return False, None, None

        except Exception as e:
            logger.error(f"Unexpected error checking for updates: {e}")
            return False, None, None

    def get_install_command(self) -> str:
        """Get the command to install the update."""
        return f"curl -fsSL https://raw.githubusercontent.com/{self.repo_owner}/{self.repo_name}/main/install.sh | bash"


def check_for_updates() -> Tuple[bool, Optional[str], Optional[str], str]:
    """
    Convenience function to check for updates.

    Returns:
        Tuple of (update_available, latest_version, download_url, install_command)
    """
    checker = UpdateChecker()
    update_available, latest_version, download_url = checker.check_for_updates()
    install_command = checker.get_install_command()

    return update_available, latest_version, download_url, install_command
