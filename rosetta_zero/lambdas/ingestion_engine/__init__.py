"""Ingestion Engine Lambda - Discovery Phase.

Analyzes legacy artifacts and extracts behavioral logic into Logic Maps.
"""

from .handler import lambda_handler
from .ingestion import IngestionEngine

__all__ = ["lambda_handler", "IngestionEngine"]
