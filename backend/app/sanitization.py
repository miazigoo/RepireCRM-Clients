import re
from typing import Any

import bleach

CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_plain_text(value: Any, *, max_length: int | None = None, strip: bool = True) -> str:
    text = bleach.clean(
        str(value),
        tags=[],
        attributes={},
        protocols=[],
        strip=True,
        strip_comments=True,
    )
    text = CONTROL_CHARS_RE.sub("", text)
    if strip:
        text = text.strip()
    if max_length is not None:
        text = text[:max_length]
    return text


def sanitize_optional_text(
    value: Any, *, max_length: int | None = None, strip: bool = True
) -> str | None:
    if value is None:
        return None
    text = sanitize_plain_text(value, max_length=max_length, strip=strip)
    return text or None


def sanitize_payload(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_plain_text(value)
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    if isinstance(value, dict):
        return {
            sanitize_plain_text(key, max_length=120): sanitize_payload(item)
            for key, item in value.items()
        }
    return value
