"""Perplexify CLI package.

Perplexify is a local terminal and HTTP wrapper around the existing
Perplexity reverse-web stack. It intentionally reuses
``ask_perplexity_async`` and never calls the official Perplexity API.
"""

from scraping_lab.perplexity_lab.perplexify.models import (
    MODEL_CHOICES,
    PerplexifyResult,
)

__all__ = ["MODEL_CHOICES", "PerplexifyResult"]
