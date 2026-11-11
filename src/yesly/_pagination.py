from typing import Any, Callable, Dict, Generic, Iterator, List, Optional, TypeVar

T = TypeVar("T")


class Page(Generic[T]):
    """One page of a list. Iterating it yields every item from this page on,
    fetching later pages as needed; ``data`` holds this page only."""

    def __init__(self, raw: Dict[str, Any], fetch_after: Callable[[str], "Page[T]"]) -> None:
        self.object: str = raw.get("object", "list")
        self.url: str = raw.get("url", "")
        self.has_more: bool = bool(raw.get("has_more"))
        self.data: List[T] = raw.get("data", [])
        self._fetch_after = fetch_after

    def _last_id(self) -> Optional[str]:
        # Lists that come whole, in one page (a conversation's turns), have items without an id.
        last: Any = self.data[-1] if self.data else None
        item_id = last.get("id") if isinstance(last, dict) else None
        return item_id if isinstance(item_id, str) else None

    def has_next_page(self) -> bool:
        return self.has_more and self._last_id() is not None

    def next_page(self) -> "Page[T]":
        """The page after this one. Check ``has_next_page()`` first."""
        last_id = self._last_id()
        if not self.has_more or last_id is None:
            raise StopIteration("There is no next page.")
        return self._fetch_after(last_id)

    def auto_paging_iter(self) -> Iterator[T]:
        page: Optional[Page[T]] = self
        while page is not None:
            yield from page.data
            page = page.next_page() if page.has_next_page() else None

    def __iter__(self) -> Iterator[T]:
        return self.auto_paging_iter()

    def __repr__(self) -> str:
        return f"<Page url={self.url!r} items={len(self.data)} has_more={self.has_more}>"
