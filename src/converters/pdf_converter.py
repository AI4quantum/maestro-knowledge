"""PDF converter."""

import logging
from io import BytesIO
from typing import Any

from .base import ContentConverter

logger = logging.getLogger(__name__)


class PDFConverter(ContentConverter):
    """Convert PDF to text using pypdf or pdfplumber."""

    @property
    def supported_types(self) -> list[str]:
        """Return supported MIME types."""
        return ["application/pdf"]

    @property
    def supported_extensions(self) -> list[str]:
        """Return supported file extensions."""
        return ["pdf"]

    @property
    def requires_dependencies(self) -> list[str]:
        """Return required dependencies."""
        # We'll try pypdf first, then pdfplumber as fallback
        return ["pypdf"]

    async def convert(self, content: bytes, metadata: dict[str, Any]) -> str:
        """Convert PDF to text.

        Args:
            content: Raw PDF content bytes
            metadata: Document metadata

        Returns:
            Extracted text from PDF

        Raises:
            ImportError: If neither pypdf nor pdfplumber is installed
            ValueError: If PDF extraction fails
        """
        # Try pypdf first (lighter dependency)
        try:
            return await self._convert_with_pypdf(content)
        except ImportError:
            logger.debug("pypdf not available, trying pdfplumber")
            pass
        except Exception as e:
            logger.warning(f"pypdf extraction failed: {e}, trying pdfplumber")
            pass

        # Fallback to pdfplumber
        try:
            return await self._convert_with_pdfplumber(content)
        except ImportError:
            raise ImportError(
                "PDF conversion requires either 'pypdf' or 'pdfplumber'. "
                "Install with: pip install pypdf"
            )
        except Exception as e:
            raise ValueError(f"Failed to extract text from PDF: {e}")

    async def _convert_with_pypdf(self, content: bytes) -> str:
        """Convert PDF using pypdf library.

        Args:
            content: Raw PDF content bytes

        Returns:
            Extracted text
        """
        import pypdf

        pdf_file = BytesIO(content)
        reader = pypdf.PdfReader(pdf_file)

        text_parts = []
        for page_num, page in enumerate(reader.pages):
            try:
                text = page.extract_text()
                if text and text.strip():
                    text_parts.append(text)
            except Exception as e:
                logger.warning(f"Failed to extract text from page {page_num}: {e}")
                continue

        if not text_parts:
            raise ValueError("No text could be extracted from PDF")

        # Join pages with double newline
        return "\n\n".join(text_parts)

    async def _convert_with_pdfplumber(self, content: bytes) -> str:
        """Convert PDF using pdfplumber library.

        Args:
            content: Raw PDF content bytes

        Returns:
            Extracted text
        """
        import pdfplumber

        pdf_file = BytesIO(content)
        text_parts = []

        with pdfplumber.open(pdf_file) as pdf:
            for page_num, page in enumerate(pdf.pages):
                try:
                    text = page.extract_text()
                    if text and text.strip():
                        text_parts.append(text)
                except Exception as e:
                    logger.warning(f"Failed to extract text from page {page_num}: {e}")
                    continue

        if not text_parts:
            raise ValueError("No text could be extracted from PDF")

        # Join pages with double newline
        return "\n\n".join(text_parts)


# Made with Bob
