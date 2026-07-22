from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from .models import JobRecord


_SPACE_RE = re.compile(r"\s+")


def _normalize_value(value: Any) -> Any:
    if isinstance(value, str):
        normalized = _SPACE_RE.sub(" ", value).strip()
        return normalized or None
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if _normalize_value(item) is not None
        }
    if isinstance(value, list | tuple):
        return [_normalize_value(item) for item in value if _normalize_value(item) is not None]
    return value


def canonical_json(payload: Mapping[str, Any]) -> str:
    normalized = _normalize_value(payload)
    return json.dumps(normalized, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def content_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def html_hash(html: str) -> str:
    return hashlib.sha256(html.encode("utf-8", errors="replace")).hexdigest()


class Tra:
    """Content-identity component.

    The explicit name keeps call sites compact while the module-level helpers
    remain available for low-level hashing work.
    """

    @staticmethod
    def hash(job: JobRecord | Mapping[str, Any]) -> str:
        payload = job.revision_payload() if isinstance(job, JobRecord) else job
        return content_hash(payload)
