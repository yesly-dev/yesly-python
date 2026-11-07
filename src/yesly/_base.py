from typing import Any
from urllib.parse import quote as _urlquote


class NotGiven:
    """Marks a keyword argument that was not passed, as opposed to ``None``,
    which is sent as ``null``."""

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "NOT_GIVEN"


NOT_GIVEN: Any = NotGiven()


def quote(value: str) -> str:
    """Encodes a path segment."""
    return _urlquote(value, safe="")


class Resource:
    def __init__(self, client: Any) -> None:
        self._client = client
