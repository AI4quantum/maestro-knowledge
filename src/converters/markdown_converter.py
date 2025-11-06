"""Markdown converter."""

from typing import Any

from .base import ContentConverter


class MarkdownConverter(ContentConverter):
    """Convert markdown files.

    Markdown is plain text, so this converter simply decodes the content.
    """

    @property
    def supported_types(self) -> list[str]:
        """Return supported MIME types."""
        return ["text/markdown", "text/x-markdown"]

    @property
    def supported_extensions(self) -> list[str]:
        """Return supported file extensions."""
        return ["md", "markdown"]

    async def convert(self, content: bytes, metadata: dict[str, Any]) -> str:
        """Convert markdown content.

        Args:
            content: Raw content bytes
            metadata: Document metadata

        Returns:
            Decoded markdown text
        """
        # Markdown is just text, decode it
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            pass

        # Try with error replacement
        try:
            return content.decode("utf-8", errors="replace")
        except Exception:
            pass

        # Fallback to latin-1
        return content.decode("latin-1", errors="replace")


# Made with Bob
