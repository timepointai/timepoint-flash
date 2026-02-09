"""Folder naming and slug sanitization for blob storage.

Generates filesystem-safe folder names from timepoint queries.

Format: {slug}_{YYYYMMDD}_{uuid6}

Examples:
    >>> from app.storage.naming import sanitize_slug, generate_folder_name
    >>> sanitize_slug("Tesla's New Yorker Hotel, 1943!")
    'teslas-new-yorker-hotel-1943'
    >>> generate_folder_name("Tesla's New Yorker Hotel, 1943!")
    'teslas-new-yorker-hotel-1943_20260209_a3f2b1'
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone


def sanitize_slug(query: str, max_length: int = 60) -> str:
    """Sanitize a query string into a filesystem-safe slug.

    Rules:
        - Lowercase
        - Strip non-alphanumeric except hyphens
        - Collapse multiple hyphens
        - Truncate to max_length
        - Fallback to 'timepoint-{uuid6}' if empty

    Args:
        query: Raw query string.
        max_length: Maximum slug length (default 60).

    Returns:
        Sanitized slug string.
    """
    slug = query.lower().strip()
    # Replace spaces and underscores with hyphens
    slug = re.sub(r"[\s_]+", "-", slug)
    # Strip everything except [a-z0-9-]
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    # Collapse multiple hyphens
    slug = re.sub(r"-{2,}", "-", slug)
    # Strip leading/trailing hyphens
    slug = slug.strip("-")
    # Truncate
    slug = slug[:max_length]
    # Strip trailing hyphen after truncation
    slug = slug.rstrip("-")
    # Fallback if empty
    if not slug:
        slug = f"timepoint-{uuid.uuid4().hex[:6]}"
    return slug


def generate_folder_name(
    query: str,
    date: datetime | None = None,
    uuid_str: str | None = None,
) -> str:
    """Generate a unique folder name for a blob.

    Format: {slug}_{YYYYMMDD}_{uuid6}

    Args:
        query: Raw query string.
        date: Override date (defaults to now UTC).
        uuid_str: Override UUID (defaults to random).

    Returns:
        Folder name string.
    """
    slug = sanitize_slug(query)
    if date is None:
        date = datetime.now(timezone.utc)
    date_str = date.strftime("%Y%m%d")
    if uuid_str is None:
        uuid_str = uuid.uuid4().hex[:6]
    else:
        uuid_str = uuid_str[:6]
    return f"{slug}_{date_str}_{uuid_str}"


def generate_folder_path(
    root: str,
    query: str,
    date: datetime | None = None,
    uuid_str: str | None = None,
) -> tuple[str, str]:
    """Generate the full folder path for a blob.

    Structure: {root}/{YYYY}/{MM}/{folder_name}/

    Args:
        root: Storage root directory.
        query: Raw query string.
        date: Override date (defaults to now UTC).
        uuid_str: Override UUID.

    Returns:
        Tuple of (full_path, folder_name).
    """
    if date is None:
        date = datetime.now(timezone.utc)
    folder_name = generate_folder_name(query, date, uuid_str)
    year = date.strftime("%Y")
    month = date.strftime("%m")
    full_path = f"{root}/{year}/{month}/{folder_name}"
    return full_path, folder_name
