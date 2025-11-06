"""HTML converter."""

from typing import Any

from .base import ContentConverter


class HTMLConverter(ContentConverter):
    """Convert HTML to markdown using html2text."""

    @property
    def supported_types(self) -> list[str]:
        """Return supported MIME types."""
        return ["text/html", "application/xhtml+xml"]

    @property
    def supported_extensions(self) -> list[str]:
        """Return supported file extensions."""
        return ["html", "htm", "xhtml"]

    @property
    def requires_dependencies(self) -> list[str]:
        """Return required dependencies."""
        return ["html2text"]

    async def convert(self, content: bytes, metadata: dict[str, Any]) -> str:
        """Convert HTML to markdown.

        Args:
            content: Raw HTML content bytes
            metadata: Document metadata

        Returns:
            Markdown text converted from HTML

        Raises:
            ImportError: If html2text is not installed
        """
        import html2text

        # Decode HTML content
        html_content = content.decode("utf-8", errors="replace")

        # Configure html2text
        h = html2text.HTML2Text()
        h.ignore_links = False  # Keep links
        h.ignore_images = False  # Keep image references
        h.body_width = 0  # Don't wrap lines

        # Convert to markdown
        return h.handle(html_content)


# Made with Bob
