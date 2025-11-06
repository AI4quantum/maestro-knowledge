"""Base class for content converters."""

from abc import ABC, abstractmethod
from typing import Any


class ContentConverter(ABC):
    """Abstract base class for content converters.

    Converters transform content from various formats (PDF, HTML, etc.)
    into plain text suitable for vector database ingestion.
    """

    @property
    @abstractmethod
    def supported_types(self) -> list[str]:
        """Return list of supported MIME types.

        Returns:
            List of MIME type strings (e.g., ['text/plain', 'text/html'])
        """
        pass

    @property
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """Return list of supported file extensions.

        Returns:
            List of file extensions without dots (e.g., ['txt', 'html'])
        """
        pass

    @abstractmethod
    async def convert(self, content: bytes, metadata: dict[str, Any]) -> str:
        """Convert content bytes to text.

        Args:
            content: Raw content bytes to convert
            metadata: Document metadata (may include hints like content_type)

        Returns:
            Converted text content

        Raises:
            ValueError: If conversion fails
        """
        pass

    @property
    def requires_dependencies(self) -> list[str]:
        """Return list of required Python packages.

        Returns:
            List of package names required for this converter
        """
        return []

    def is_available(self) -> bool:
        """Check if converter dependencies are available.

        Returns:
            True if all required dependencies are installed
        """
        for dep in self.requires_dependencies:
            try:
                __import__(dep)
            except ImportError:
                return False
        return True

    @property
    def name(self) -> str:
        """Return converter name.

        Returns:
            Human-readable converter name
        """
        return self.__class__.__name__.replace("Converter", "")


# Made with Bob
