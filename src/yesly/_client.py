import json
import os
import platform
import random
import time
import uuid
from types import ModuleType
from urllib.parse import urlsplit
from typing import Any, Dict, List, Optional, Tuple, cast

import httpx

from . import webhooks as _webhooks
from ._base import NotGiven
from ._errors import APIConnectionError, YeslyError, error_from_response
from ._generated.resources import Resources
from ._generated.types import API_VERSION, BASE_URL
from ._pagination import Page
from ._version import __version__


def _retryable(status: int) -> bool:
    return status == 408 or status == 429 or status >= 500


class Yesly(Resources):
    """Client for the Yesly API.

    The key defaults to the ``YESLY_API_KEY`` environment variable. Live keys
    start with ``ysk_live_`` and test keys with ``ysk_test_``.
    """

    webhooks: ModuleType = _webhooks
    """Webhook signature checks: ``construct_event`` and ``verify_signature``."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        api_version: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 2,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("YESLY_API_KEY") or None
        self.base_url = _check_base_url((base_url or os.environ.get("YESLY_BASE_URL") or BASE_URL).rstrip("/"))
        self.api_version = api_version or API_VERSION
        self.timeout = timeout
        self.max_retries = max_retries
        self._owns_http = http_client is None
        self._http = http_client or httpx.Client(timeout=timeout)
        self._init_resources()

    @property
    def mode(self) -> Optional[str]:
        """``live`` or ``test``, from the key's prefix."""
        if self.api_key and self.api_key.startswith("ysk_live_"):
            return "live"
        if self.api_key and self.api_key.startswith("ysk_test_"):
            return "test"
        return None

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> "Yesly":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        query: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
        idempotent: bool = False,
        idempotency_key: Optional[str] = None,
        paged: bool = False,
    ) -> Any:
        if not self.api_key:
            raise YeslyError("No API key. Pass one to Yesly(...) or set YESLY_API_KEY.")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Yesly-Version": self.api_version,
            "User-Agent": f"yesly-python/{__version__} python/{platform.python_version()}",
        }
        content = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            content = json.dumps({k: v for k, v in body.items() if not isinstance(v, NotGiven)})
        if idempotent:
            headers["Idempotency-Key"] = idempotency_key or str(uuid.uuid4())
        params = _flatten(query or {})

        attempt = 0
        while True:
            try:
                response = self._http.request(method, self.base_url + path, params=cast(Any, params), content=content, headers=headers, timeout=self.timeout)
            except httpx.TransportError as e:
                if attempt < self.max_retries:
                    time.sleep(_backoff(attempt))
                    attempt += 1
                    continue
                timed_out = isinstance(e, httpx.TimeoutException)
                raise APIConnectionError(
                    f"The request timed out after {self.timeout} s." if timed_out else "Could not reach the Yesly API."
                ) from e
            data = _parse(response)
            if response.is_success:
                break
            if _retryable(response.status_code) and attempt < self.max_retries:
                time.sleep(_retry_after(response) or _backoff(attempt))
                attempt += 1
                continue
            raise error_from_response(response, data)

        if not paged:
            return data

        def fetch_after(last_id: str) -> Page[Any]:
            return self._request(method, path, query={**(query or {}), "starting_after": last_id}, paged=True)  # type: ignore[no-any-return]

        return Page(data, fetch_after)


def _check_base_url(base_url: str) -> str:
    """The API key goes in every request, so the base URL must be HTTPS; plain HTTP only to this machine."""
    try:
        url = urlsplit(base_url)
        host = url.hostname
    except ValueError:
        raise YeslyError("The base URL is not a valid URL.") from None
    if url.scheme == "https" and host:
        return base_url
    if url.scheme == "http" and host in ("localhost", "127.0.0.1", "::1"):
        return base_url
    raise YeslyError("The base URL must use https:// (http:// is only allowed for localhost).")


def _flatten(query: Dict[str, Any]) -> List[Tuple[str, str]]:
    """``metadata={"k": "v"}`` becomes ``metadata[k]=v``; unset values are left out."""
    out: List[Tuple[str, str]] = []

    def scalar(v: Any) -> str:
        return ("true" if v else "false") if isinstance(v, bool) else str(v)

    for k, v in query.items():
        if v is None or isinstance(v, NotGiven):
            continue
        if isinstance(v, dict):
            out.extend((f"{k}[{sk}]", scalar(sv)) for sk, sv in v.items() if sv is not None)
        elif isinstance(v, (list, tuple)):
            out.extend((k, scalar(x)) for x in v)
        else:
            out.append((k, scalar(v)))
    return out


def _parse(response: httpx.Response) -> Any:
    if not response.content:
        return None
    try:
        return response.json()
    except ValueError:
        return None


def _retry_after(response: httpx.Response) -> Optional[float]:
    try:
        s = float(response.headers.get("retry-after", ""))
    except ValueError:
        return None
    return s if 0 <= s <= 60 else None


def _backoff(attempt: int) -> float:
    base: float = min(0.5 * 2.0**attempt, 8.0)
    return base / 2 + random.random() * base / 2
