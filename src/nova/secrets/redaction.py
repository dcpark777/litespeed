"""Transcript redaction filter — SPEC §16.3(2). Applied at NovaEvent ingestion,
before events reach T1/T2. Belt-and-suspenders: structurally, secrets shouldn't
enter agent context at all; this catches the day one leaks into a tool result.

Also reused by the memory promotion gate (§16.3(3)).
"""
from __future__ import annotations

import re

REDACTED = "[REDACTED]"

_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"AKIA[0-9A-Z]{16}"),                       # AWS access key id
    re.compile(r"(?i)aws_secret_access_key\s*[=:]\s*\S+"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),             # GitHub tokens
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}"),  # JWT
    re.compile(r"(?i)authorization:\s*(bearer|basic)\s+\S+"),
    re.compile(r"(?i)(api[_-]?key|token|password)\s*[=:]\s*['\"]?[A-Za-z0-9_\-/+]{16,}"),
]


def scrub(text: str) -> str:
    for pat in _PATTERNS:
        text = pat.sub(REDACTED, text)
    return text


def contains_secret(text: str) -> bool:
    return any(p.search(text) for p in _PATTERNS)
