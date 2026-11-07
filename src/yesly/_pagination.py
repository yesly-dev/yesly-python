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

    def has_next_page(self) -> bool:
        return self.has_more and len(self.data) > 0

    def next_page(self) -> "Page[T]":
        """The page after this one. Check ``has_next_page()`` first."""
        if not self.has_next_page():
            raise StopIteration("There is no next page.")
        last: Any = self.data[-1]
        return self._fetch_after(last["id"])

    def auto_paging_iter(self) -> Iterator[T]:
        page: Optional[Page[T]] = self
        while page is not None:
            yield from page.data
            page = page.next_page() if page.has_next_page() else None

    def __iter__(self) -> Iterator[T]:
        return self.auto_paging_iter()

    def __repr__(self) -> str:
        return f"<Page url={self.url!r} items={len(self.data)} has_more={self.has_more}>"
