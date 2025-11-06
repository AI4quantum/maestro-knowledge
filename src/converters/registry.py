"""Converter registry for managing content converters."""

import logging
from typing import Optional

from .base import ContentConverter

logger = logging.getLogger(__name__)


class ConverterRegistry:
    """Registry for content converters.

    Manages registration and lookup of converters by content type
    and file extension.
    """

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._converters: dict[str, ContentConverter] = {}
        self._extension_map: dict[str, str] = {}
        self._mime_map: dict[str, str] = {}

    def register(self, name: str, converter: ContentConverter) -> None:
        """Register a converter.

        Args:
            name: Unique name for the converter
            converter: ContentConverter instance to register
        """
        if not converter.is_available():
            logger.warning(
                f"Converter '{name}' dependencies not available, skipping registration"
            )
            return

        self._converters[name] = converter

        # Build lookup maps
        for ext in converter.supported_extensions:
            self._extension_map[ext.lower()] = name
        for mime in converter.supported_types:
            self._mime_map[mime.lower()] = name

        logger.debug(f"Registered converter '{name}' for {converter.supported_types}")

    def get_converter(
        self,
        content_type: Optional[str] = None,
        extension: Optional[str] = None,
    ) -> Optional[ContentConverter]:
        """Get appropriate converter for content.

        Args:
            content_type: MIME type of content
            extension: File extension (with or without leading dot)

        Returns:
            ContentConverter instance or None if no suitable converter found
        """
        # Try explicit content type first
        if content_type:
            # Remove charset and other parameters
            mime = content_type.split(";")[0].strip().lower()
            name = self._mime_map.get(mime)
            if name:
                return self._converters.get(name)

        # Try file extension
        if extension:
            ext = extension.lower().lstrip(".")
            name = self._extension_map.get(ext)
            if name:
                return self._converters.get(name)

        # Return fallback converter if available
        return self._converters.get("fallback")

    def list_converters(self) -> list[str]:
        """List all registered converter names.

        Returns:
            List of converter names
        """
        return list(self._converters.keys())

    def get_supported_types(self) -> list[str]:
        """Get all supported MIME types.

        Returns:
            List of supported MIME types
        """
        return list(self._mime_map.keys())

    def get_supported_extensions(self) -> list[str]:
        """Get all supported file extensions.

        Returns:
            List of supported extensions
        """
        return list(self._extension_map.keys())


# Global registry instance
_global_registry: Optional[ConverterRegistry] = None


def get_converter_registry() -> ConverterRegistry:
    """Get the global converter registry instance.

    Returns:
        Global ConverterRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ConverterRegistry()
        _register_default_converters(_global_registry)
    return _global_registry


def _register_default_converters(registry: ConverterRegistry) -> None:
    """Register default converters.

    Args:
        registry: ConverterRegistry to register converters with
    """
    # Import and register converters
    # These imports are done here to avoid circular dependencies
    # and to allow graceful degradation if dependencies are missing

    try:
        from .text_converter import TextConverter

        registry.register("text", TextConverter())
    except ImportError as e:
        logger.warning(f"Failed to register text converter: {e}")

    try:
        from .markdown_converter import MarkdownConverter

        registry.register("markdown", MarkdownConverter())
    except ImportError as e:
        logger.warning(f"Failed to register markdown converter: {e}")

    try:
        from .html_converter import HTMLConverter

        registry.register("html", HTMLConverter())
    except ImportError as e:
        logger.warning(f"Failed to register HTML converter: {e}")

    try:
        from .pdf_converter import PDFConverter

        registry.register("pdf", PDFConverter())
    except ImportError as e:
        logger.warning(f"Failed to register PDF converter: {e}")

    try:
        from .fallback_converter import FallbackConverter

        registry.register("fallback", FallbackConverter())
    except ImportError as e:
        logger.warning(f"Failed to register fallback converter: {e}")


# Made with Bob
