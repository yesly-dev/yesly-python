from typing import Any, Dict, Mapping, Optional

import httpx


class YeslyError(Exception):
    """Base class of every error this library raises."""

    def __init__(
        self,
        message: str,
        *,
        status: Optional[int] = None,
        type: Optional[str] = None,
        code: Optional[str] = None,
        param: Optional[str] = None,
        request_id: Optional[str] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        #: HTTP status, when the API answered.
        self.status = status
        #: Error class from the API, such as ``invalid_request``.
        self.type = type
        #: Machine-readable reason, such as ``phone_invalid``.
        self.code = code
        #: The parameter at fault, such as ``customer.phone``.
        self.param = param
        #: ``Request-Id`` of the failed request; include it when you contact support.
        self.request_id = request_id
        self.headers = headers


class InvalidRequestError(YeslyError):
    """400 and other 4xx answers: something in the request needs fixing."""


class AuthenticationError(YeslyError):
    """401: missing or revoked API key."""


class PermissionDeniedError(YeslyError):
    """403: the key cannot reach this resource, or the IP is not allowed."""


class NotFoundError(YeslyError):
    """404: no such object in this account and mode."""


class ConflictError(YeslyError):
    """409: such as an ``external_id`` already used with different data."""


class RateLimitError(YeslyError):
    """429: too many requests. Retried automatically before this is raised."""


class APIError(YeslyError):
    """5xx: something went wrong on Yesly's side. Retried automatically before this is raised."""


class APIConnectionError(YeslyError):
    """The request did not get an answer: network failure or timeout."""


class SignatureVerificationError(YeslyError):
    """A webhook delivery whose ``Yesly-Signature`` does not match, or is too old."""


def error_from_response(response: httpx.Response, body: Any) -> YeslyError:
    e: Dict[str, Any] = body["error"] if isinstance(body, dict) and isinstance(body.get("error"), dict) else {}
    status = response.status_code
    message = e.get("message") or f"The Yesly API answered {status}."
    cls = {401: AuthenticationError, 403: PermissionDeniedError, 404: NotFoundError, 409: ConflictError, 429: RateLimitError}.get(status)
    if cls is None:
        cls = APIError if status >= 500 else InvalidRequestError
    return cls(
        message,
        status=status,
        type=e.get("type"),
        code=e.get("code"),
        param=e.get("param"),
        request_id=e.get("request_id") or response.headers.get("request-id"),
        headers=response.headers,
    )
