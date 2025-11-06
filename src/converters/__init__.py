"""Content converter package for document ingestion.

This package provides pluggable converters for various document formats
including text, markdown, HTML, and PDF.
"""

from .base import ContentConverter
from .registry import ConverterRegistry, get_converter_registry
from .detector import ContentDetector
from .fetcher import DocumentFetcher

__all__ = [
    "ContentConverter",
    "ConverterRegistry",
    "get_converter_registry",
    "ContentDetector",
    "DocumentFetcher",
]

# Made with Bob
