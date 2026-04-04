"""
Utility functions for the application.
"""

import re
from uuid import uuid4


def create_slug(name: str) -> str:
    """
    Create URL-safe slug from tenant name.

    Converts to lowercase, replaces non-alphanumeric characters with hyphens,
    and strips leading/trailing hyphens.

    Args:
        name: The tenant name to convert

    Returns:
        URL-safe slug string

    Raises:
        ValueError: If name is empty or contains only whitespace

    Examples:
        >>> create_slug("Acme Corporation")
        'acme-corporation'
        >>> create_slug("Tech & Co.")
        'tech-co'
        >>> create_slug("O'Reilly Media")
        'o-reilly-media'
    """
    if not name or not name.strip():
        raise ValueError("Tenant name cannot be empty")

    slug = name.lower()
    # Replace all non-alphanumeric characters with hyphens
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    # Remove leading/trailing hyphens
    slug = slug.strip("-")

    # Handle edge case where only special characters were present
    if not slug:
        slug = f"tenant-{uuid4().hex[:8]}"

    return slug
