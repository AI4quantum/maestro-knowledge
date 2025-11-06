"""Document fetcher for URLs and local files."""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


class DocumentFetcher:
    """Fetch documents from URLs or local files.

    Security: Local file access is restricted to allowed directories to prevent
    unauthorized file system access (e.g., /etc/passwd). Configure allowed paths
    via MAESTRO_ALLOWED_FILE_PATHS environment variable.
    """

    def __init__(
        self, timeout: int = 30, allowed_paths: list[str] | None = None
    ) -> None:
        """Initialize fetcher.

        Args:
            timeout: Timeout in seconds for HTTP requests
            allowed_paths: List of allowed directory paths for file:// access.
                          If None, uses MAESTRO_ALLOWED_FILE_PATHS env var.
                          If env var not set, defaults to current working directory.
        """
        self.timeout = timeout

        # Configure allowed paths for file access
        if allowed_paths is None:
            # Try environment variable first
            env_paths = os.environ.get("MAESTRO_ALLOWED_FILE_PATHS", "")
            if env_paths:
                # Split on : (Unix) or ; (Windows)
                separator = ";" if os.name == "nt" else ":"
                allowed_paths = [
                    p.strip() for p in env_paths.split(separator) if p.strip()
                ]
            else:
                # Default to current working directory only
                allowed_paths = [os.getcwd()]

        # Convert to absolute paths and resolve symlinks
        self.allowed_paths = [str(Path(p).resolve()) for p in allowed_paths]

        logger.info(f"File access restricted to: {self.allowed_paths}")

    async def fetch(self, url: str) -> tuple[bytes, dict[str, Any]]:
        """Fetch document content from URL or local file.

        Args:
            url: URL (http/https/file) or local file path

        Returns:
            Tuple of (content_bytes, metadata_dict)

        Raises:
            ValueError: If URL scheme is unsupported
            httpx.HTTPError: If HTTP request fails
            FileNotFoundError: If local file not found
        """
        parsed = urlparse(url)

        if parsed.scheme in ("http", "https"):
            return await self._fetch_http(url)
        elif parsed.scheme == "file" or not parsed.scheme:
            return await self._fetch_file(url)
        else:
            raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")

    async def _fetch_http(self, url: str) -> tuple[bytes, dict[str, Any]]:
        """Fetch from HTTP/HTTPS URL.

        Args:
            url: HTTP or HTTPS URL

        Returns:
            Tuple of (content_bytes, metadata_dict)
        """
        logger.debug(f"Fetching HTTP URL: {url}")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url, follow_redirects=True, timeout=self.timeout
            )
            response.raise_for_status()

            metadata = {
                "content_type": response.headers.get("content-type"),
                "content_length": response.headers.get("content-length"),
                "last_modified": response.headers.get("last-modified"),
                "fetched_at": datetime.utcnow().isoformat(),
            }

            logger.debug(
                f"Fetched {len(response.content)} bytes from {url}, "
                f"content_type={metadata['content_type']}"
            )

            return response.content, metadata

    async def _fetch_file(self, url: str) -> tuple[bytes, dict[str, Any]]:
        """Fetch from local file.

        Args:
            url: File URL (file://) or plain file path

        Returns:
            Tuple of (content_bytes, metadata_dict)

        Raises:
            PermissionError: If file path is outside allowed directories
            FileNotFoundError: If file doesn't exist
        """
        # Handle file:// URLs and plain paths
        if url.startswith("file://"):
            path = url.replace("file://", "")
        else:
            path = url

        # Resolve to absolute path and check against allowed paths
        abs_path = str(Path(path).resolve())

        # Security check: Ensure path is within allowed directories
        if not self._is_path_allowed(abs_path):
            allowed_str = ", ".join(self.allowed_paths)
            raise PermissionError(
                f"Access denied: '{abs_path}' is outside allowed directories. "
                f"Allowed paths: {allowed_str}. "
                f"Configure via MAESTRO_ALLOWED_FILE_PATHS environment variable."
            )

        logger.debug(f"Reading local file: {abs_path}")

        # Read file synchronously (aiofiles would be better but adds dependency)
        with open(abs_path, "rb") as f:
            content = f.read()

        stat = os.stat(abs_path)
        metadata = {
            "content_length": str(stat.st_size),
            "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "fetched_at": datetime.utcnow().isoformat(),
        }

        logger.debug(f"Read {len(content)} bytes from {abs_path}")

        return content, metadata

    def _is_path_allowed(self, path: str) -> bool:
        """Check if a path is within allowed directories.

        Args:
            path: Absolute path to check

        Returns:
            True if path is within an allowed directory
        """
        path_obj = Path(path)

        for allowed in self.allowed_paths:
            allowed_obj = Path(allowed)
            try:
                # Check if path is relative to allowed directory
                path_obj.relative_to(allowed_obj)
                return True
            except ValueError:
                # Not relative to this allowed path, try next
                continue

        return False


# Made with Bob
