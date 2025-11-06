"""Plain text converter."""

from typing import Any

from .base import ContentConverter


class TextConverter(ContentConverter):
    """Convert plain text files."""

    @property
    def supported_types(self) -> list[str]:
        """Return supported MIME types."""
        return ["text/plain"]

    @property
    def supported_extensions(self) -> list[str]:
        """Return supported file extensions."""
        return ["txt", "text"]

    async def convert(self, content: bytes, metadata: dict[str, Any]) -> str:
        """Convert text content.

        Args:
            content: Raw content bytes
            metadata: Document metadata

        Returns:
            Decoded text content
        """
        # Try UTF-8 first (most common)
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            pass

        # Try UTF-8 with error replacement
        try:
            return content.decode("utf-8", errors="replace")
        except Exception:
            pass

        # Fallback to latin-1 (never fails)
        return content.decode("latin-1", errors="replace")


# Made with Bob
