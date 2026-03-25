"""Prompt input sanitization utilities.

Strips and escapes user-controlled input before it is injected into prompt
templates via str.format().  Two threat classes are addressed:

1. Format-string injection — any literal ``{`` or ``}`` in user input would be
   interpreted by str.format() as a placeholder, causing KeyError or silent
   variable substitution.  We escape them to ``{{`` / ``}}`` so they pass
   through format() unchanged.

2. Prompt-injection attacks — adversarial instructions (e.g. "Ignore previous
   instructions", "SYSTEM: …") that attempt to override the pipeline's system
   prompt and steer the model toward unintended behaviour.  Recognised patterns
   are replaced with a neutral placeholder.

Usage::

    from app.prompts.sanitize import sanitize_prompt_input

    query = sanitize_prompt_input(raw_query)
"""

from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------------------
# Injection pattern detection
# ---------------------------------------------------------------------------

# Phrases associated with prompt-injection attempts.  Matching is
# case-insensitive and allows for simple Unicode lookalike substitutions by
# normalising to NFC first.
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?|context|text)",
        r"disregard\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?|context|text)",
        r"forget\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?|context|text)",
        r"override\s+(all\s+)?(previous|prior|above)?\s*(instructions?|prompts?|rules?|context)",
        # Role-hijack attempts
        r"\byou\s+are\s+now\b",
        r"\bact\s+as\s+(?:a\s+)?(?:different|new|another|an?\s+unrestricted)",
        r"\bpretend\s+(?:you\s+are|to\s+be)\b",
        r"\bnew\s+persona\b",
        r"\bdo\s+anything\s+now\b",
        r"\bdan\b.*\bmode\b",
        # Fake role markers injected into user text
        r"(?:^|\n)\s*(?:system|assistant|user)\s*:\s*",
        r"(?:^|\n)\s*<\s*(?:system|assistant|user)\s*>",
        r"(?:^|\n)\s*\[INST\]",
        r"(?:^|\n)\s*###\s*(?:system|instruction)",
        # Exfiltration / leaking attempts
        r"\brepeat\s+(back\s+|verbatim\s+)?(?:your\s+)?(?:system|initial|original|above)\s+prompt",
        r"\bprint\s+(?:your\s+)?(?:system|initial|original)\s+prompt",
        r"\bwhat\s+(?:are\s+)?your\s+(?:instructions?|system\s+prompt)",
    ]
]

_PLACEHOLDER = "[input removed]"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def sanitize_prompt_input(value: str, *, max_length: int = 4000) -> str:
    """Sanitize a user-supplied string before it is placed in a prompt template.

    Steps applied in order:
    1. Coerce to ``str`` and NFC-normalise Unicode.
    2. Remove null bytes and ASCII control characters (except newline/tab).
    3. Escape literal ``{`` and ``}`` so str.format() treats them as text.
    4. Replace recognised prompt-injection patterns with ``[input removed]``.
    5. Truncate to *max_length* characters.

    Args:
        value: The raw user input string.
        max_length: Hard character limit applied after all other transforms.
            Defaults to 4 000 characters, sufficient for any single field.

    Returns:
        Sanitized string safe for use inside a str.format() call.
    """
    if not isinstance(value, str):
        value = str(value)

    # Step 1 — Unicode normalisation (collapses lookalike characters)
    value = unicodedata.normalize("NFC", value)

    # Step 2 — strip null bytes and non-printable ASCII control chars
    # Keep \t (0x09) and \n (0x0A); strip everything else below 0x20 plus DEL.
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)

    # Step 3 — escape format-string metacharacters
    value = value.replace("{", "{{").replace("}", "}}")

    # Step 4 — neutralise prompt-injection patterns
    for pattern in _INJECTION_PATTERNS:
        value = pattern.sub(_PLACEHOLDER, value)

    # Step 5 — enforce length cap
    if len(value) > max_length:
        value = value[:max_length]

    return value
