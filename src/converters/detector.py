"""Content type detection utilities."""

import mimetypes
from typing import Optional
from urllib.parse import urlparse


class ContentDetector:
    """Detect content type from various sources."""

    # MIME type mappings for common extensions
    MIME_MAP = {
        "txt": "text/plain",
        "text": "text/plain",
        "md": "text/markdown",
        "markdown": "text/markdown",
        "html": "text/html",
        "htm": "text/html",
        "xhtml": "application/xhtml+xml",
        "pdf": "application/pdf",
    }

    @staticmethod
    def from_url(url: str) -> tuple[Optional[str], Optional[str]]:
        """Detect content type and extension from URL.

        Args:
            url: URL or file path to analyze

        Returns:
            Tuple of (content_type, extension) where either may be None
        """
        parsed = urlparse(url)
        path = parsed.path

        # Extract extension
        ext = None
        if "." in path:
            ext = path.rsplit(".", 1)[1].lower()

        # Map extension to MIME type
        content_type = ContentDetector.MIME_MAP.get(ext) if ext else None

        # Fallback to mimetypes module
        if not content_type and ext:
            guessed_type, _ = mimetypes.guess_type(f"file.{ext}")
            content_type = guessed_type

        return content_type, ext

    @staticmethod
    def from_response_headers(headers: dict[str, str]) -> Optional[str]:
        """Detect content type from HTTP response headers.

        Args:
            headers: HTTP response headers dict

        Returns:
            Content type string or None
        """
        content_type = headers.get("content-type", headers.get("Content-Type", ""))
        if content_type:
            # Remove charset and other parameters
            return content_type.split(";")[0].strip()
        return None

    @staticmethod
    def from_content(content: bytes) -> Optional[str]:
        """Detect content type from content magic bytes.

        Args:
            content: Content bytes to analyze

        Returns:
            Content type string or None
        """
        if not content:
            return None

        # PDF magic bytes
        if content.startswith(b"%PDF"):
            return "application/pdf"

        # HTML detection (look for common HTML tags)
        try:
            text_start = content[:1000].decode("utf-8", errors="ignore").lower()
            if any(
                tag in text_start
                for tag in ["<html", "<!doctype html", "<head", "<body"]
            ):
                return "text/html"
        except Exception:
            pass

        # Try to decode as text
        try:
            content.decode("utf-8")
            return "text/plain"
        except UnicodeDecodeError:
            pass

        return None

    @staticmethod
    def detect(
        url: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
        content: Optional[bytes] = None,
        explicit_type: Optional[str] = None,
    ) -> tuple[Optional[str], Optional[str]]:
        """Detect content type using all available information.

        Tries detection methods in order of reliability:
        1. Explicit type override
        2. Response headers
        3. URL/filename extension
        4. Content magic bytes

        Args:
            url: URL or file path
            headers: HTTP response headers
            content: Content bytes
            explicit_type: Explicit content type override

        Returns:
            Tuple of (content_type, extension)
        """
        content_type = None
        extension = None

        # 1. Explicit type override
        if explicit_type:
            content_type = explicit_type

        # 2. Response headers
        if not content_type and headers:
            content_type = ContentDetector.from_response_headers(headers)

        # 3. URL/filename extension
        if url:
            url_type, url_ext = ContentDetector.from_url(url)
            if not content_type:
                content_type = url_type
            if not extension:
                extension = url_ext

        # 4. Content magic bytes
        if not content_type and content:
            content_type = ContentDetector.from_content(content)

        return content_type, extension


# Made with Bob
