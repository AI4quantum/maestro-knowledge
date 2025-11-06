"""Tests for document converters."""

import pytest

from src.converters import (
    ContentConverter,
    ContentDetector,
    DocumentFetcher,
    get_converter_registry,
)


class TestContentDetector:
    """Test content type detection."""

    def test_detect_from_url_pdf(self) -> None:
        """Test PDF detection from URL."""
        detector = ContentDetector()
        content_type, ext = detector.from_url("https://example.com/document.pdf")
        assert content_type == "application/pdf"
        assert ext == "pdf"

    def test_detect_from_url_html(self) -> None:
        """Test HTML detection from URL."""
        detector = ContentDetector()
        content_type, ext = detector.from_url("https://example.com/page.html")
        assert content_type == "text/html"
        assert ext == "html"

    def test_detect_from_url_markdown(self) -> None:
        """Test Markdown detection from URL."""
        detector = ContentDetector()
        content_type, ext = detector.from_url("https://example.com/README.md")
        assert content_type == "text/markdown"
        assert ext == "md"

    def test_detect_from_url_text(self) -> None:
        """Test text detection from URL."""
        detector = ContentDetector()
        content_type, ext = detector.from_url("https://example.com/notes.txt")
        assert content_type == "text/plain"
        assert ext == "txt"

    def test_detect_from_content_pdf(self) -> None:
        """Test PDF detection from content magic bytes."""
        detector = ContentDetector()
        pdf_content = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3"
        content_type = detector.from_content(pdf_content)
        assert content_type == "application/pdf"

    def test_detect_from_content_text(self) -> None:
        """Test text detection from content."""
        detector = ContentDetector()
        text_content = b"This is plain text content"
        content_type = detector.from_content(text_content)
        assert content_type == "text/plain"

    def test_detect_from_response_headers(self) -> None:
        """Test detection from HTTP headers."""
        detector = ContentDetector()
        headers = {"content-type": "application/pdf; charset=utf-8"}
        content_type = detector.from_response_headers(headers)
        assert content_type == "application/pdf"


class TestConverterRegistry:
    """Test converter registry."""

    def test_registry_initialization(self) -> None:
        """Test that registry initializes with default converters."""
        registry = get_converter_registry()
        converters = registry.list_converters()

        # Should have at least text, markdown, and fallback
        assert "text" in converters
        assert "markdown" in converters
        assert "fallback" in converters

    def test_get_converter_by_extension(self) -> None:
        """Test getting converter by file extension."""
        registry = get_converter_registry()

        # Test text converter
        converter = registry.get_converter(extension="txt")
        assert converter is not None
        assert "text" in converter.name.lower()

    def test_get_converter_by_content_type(self) -> None:
        """Test getting converter by MIME type."""
        registry = get_converter_registry()

        # Test markdown converter
        converter = registry.get_converter(content_type="text/markdown")
        assert converter is not None
        assert "markdown" in converter.name.lower()

    def test_get_converter_fallback(self) -> None:
        """Test fallback converter for unknown types."""
        registry = get_converter_registry()

        # Unknown type should return fallback
        converter = registry.get_converter(
            content_type="application/unknown", extension="xyz"
        )
        assert converter is not None
        assert "fallback" in converter.name.lower()

    def test_supported_types(self) -> None:
        """Test getting all supported types."""
        registry = get_converter_registry()
        types = registry.get_supported_types()

        # Always available
        assert "text/plain" in types
        assert "text/markdown" in types

        # May not be available if html2text not installed
        # assert "text/html" in types

    def test_supported_extensions(self) -> None:
        """Test getting all supported extensions."""
        registry = get_converter_registry()
        extensions = registry.get_supported_extensions()

        # Always available
        assert "txt" in extensions
        assert "md" in extensions

        # May not be available if html2text not installed
        # assert "html" in extensions


class TestTextConverter:
    """Test text converter."""

    @pytest.mark.asyncio
    async def test_convert_utf8(self) -> None:
        """Test converting UTF-8 text."""
        registry = get_converter_registry()
        converter = registry.get_converter(content_type="text/plain")

        content = "Hello, World!".encode("utf-8")
        result = await converter.convert(content, {})

        assert result == "Hello, World!"

    @pytest.mark.asyncio
    async def test_convert_with_special_chars(self) -> None:
        """Test converting text with special characters."""
        registry = get_converter_registry()
        converter = registry.get_converter(content_type="text/plain")

        content = "Hello, 世界! 🌍".encode("utf-8")
        result = await converter.convert(content, {})

        assert "Hello" in result
        assert "世界" in result


class TestMarkdownConverter:
    """Test markdown converter."""

    @pytest.mark.asyncio
    async def test_convert_markdown(self) -> None:
        """Test converting markdown content."""
        registry = get_converter_registry()
        converter = registry.get_converter(content_type="text/markdown")

        content = "# Hello\n\nThis is **markdown**.".encode("utf-8")
        result = await converter.convert(content, {})

        assert "# Hello" in result
        assert "**markdown**" in result


class TestHTMLConverter:
    """Test HTML converter."""

    @pytest.mark.asyncio
    async def test_convert_html(self) -> None:
        """Test converting HTML to markdown."""
        registry = get_converter_registry()
        converter = registry.get_converter(content_type="text/html")

        if converter is None:
            pytest.skip("HTML converter not available (html2text not installed)")

        html_content = "<html><body><h1>Hello</h1><p>World</p></body></html>"
        content = html_content.encode("utf-8")
        result = await converter.convert(content, {})

        # Should convert to markdown-like format
        assert "Hello" in result
        assert "World" in result


class TestPDFConverter:
    """Test PDF converter."""

    @pytest.mark.asyncio
    async def test_pdf_converter_availability(self) -> None:
        """Test PDF converter availability."""
        registry = get_converter_registry()
        converter = registry.get_converter(content_type="application/pdf")

        # PDF converter may not be available if pypdf/pdfplumber not installed
        # In that case, fallback converter is used
        assert converter is not None

        # Check if it's PDF or fallback
        converter_name = converter.name.lower()
        assert "pdf" in converter_name or "fallback" in converter_name


class TestFallbackConverter:
    """Test fallback converter."""

    @pytest.mark.asyncio
    async def test_fallback_converts_text(self) -> None:
        """Test fallback converter handles text."""
        registry = get_converter_registry()
        converter = registry.get_converter(content_type="application/unknown")

        content = "Plain text content".encode("utf-8")
        result = await converter.convert(content, {})

        assert result == "Plain text content"


# Made with Bob
