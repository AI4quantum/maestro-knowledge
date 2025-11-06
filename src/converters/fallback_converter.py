"""Fallback converter for unknown content types."""

import logging
from typing import Any

from .base import ContentConverter

logger = logging.getLogger(__name__)


class FallbackConverter(ContentConverter):
    """Fallback converter that attempts basic text extraction.

    This converter is used when no specific converter is available
    for the content type. It attempts to decode the content as text.
    """

    @property
    def supported_types(self) -> list[str]:
        """Return supported MIME types (accepts all)."""
        return ["*/*"]

    @property
    def supported_extensions(self) -> list[str]:
        """Return supported file extensions (accepts all)."""
        return ["*"]

    async def convert(self, content: bytes, metadata: dict[str, Any]) -> str:
        """Attempt to convert unknown content to text.

        Args:
            content: Raw content bytes
            metadata: Document metadata

        Returns:
            Decoded text content (best effort)

        Raises:
            ValueError: If content cannot be decoded as text
        """
        logger.warning(
            f"Using fallback converter for content type: "
            f"{metadata.get('content_type', 'unknown')}"
        )

        # Try UTF-8
        try:
            text = content.decode("utf-8")
            logger.debug("Successfully decoded as UTF-8")
            return text
        except UnicodeDecodeError:
            pass

        # Try UTF-8 with error replacement
        try:
            text = content.decode("utf-8", errors="replace")
            logger.debug("Decoded as UTF-8 with error replacement")
            return text
        except Exception:
            pass

        # Try latin-1 (never fails but may produce garbage)
        try:
            text = content.decode("latin-1", errors="replace")
            logger.debug("Decoded as latin-1 with error replacement")
            return text
        except Exception as e:
            raise ValueError(f"Failed to decode content as text: {e}")


# Made with Bob
