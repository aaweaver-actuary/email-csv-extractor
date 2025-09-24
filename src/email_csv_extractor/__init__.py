"""Email CSV Extractor - Auto CSV log file ingestion from email to Microsoft Teams."""

__version__ = "0.1.0"
__author__ = "Andrew Weaver"
__email__ = "andrewayersweaver+github@gmail.com"

from .core.container import DependencyContainer
from .core.exceptions import EmailCsvExtractorError

__all__ = ["DependencyContainer", "EmailCsvExtractorError"]