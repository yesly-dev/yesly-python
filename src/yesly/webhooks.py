"""Webhook signature checks. They need the endpoint's signing secret
(``whsec_…``), not an API key."""

import hashlib
import hmac
import json
import time
from typing import Optional, Union, cast

from ._errors import SignatureVerificationError
from ._generated.types import Event

DEFAULT_TOLERANCE = 300
"""Seconds a delivery's timestamp may differ from the local clock."""


def verify_signature(
    payload: Union[str, bytes],
    header: Optional[str],
    secret: str,
    *,
    tolerance: int = DEFAULT_TOLERANCE,
    now: Optional[int] = None,
) -> None:
    """Checks a delivery's ``Yesly-Signature`` header against the raw body.

    Raises ``SignatureVerificationError`` when no signature matches or the
    timestamp is more than ``tolerance`` seconds away (0 turns that check off).
    """
    if not header:
        raise SignatureVerificationError("The Yesly-Signature header is missing.")
    timestamp: Optional[int] = None
    signatures = []
    for part in header.split(","):
        key, _, value = part.strip().partition("=")
        if key == "t":
            try:
                timestamp = int(value)
            except ValueError:
                timestamp = None
        elif key == "v1":
            signatures.append(value)
    if timestamp is None or not signatures:
        raise SignatureVerificationError("The Yesly-Signature header is malformed.")
    current = int(time.time()) if now is None else now
    if tolerance > 0 and abs(current - timestamp) > tolerance:
        raise SignatureVerificationError("The Yesly-Signature timestamp is outside the tolerance.")
    body = payload.encode("utf-8") if isinstance(payload, str) else payload
    expected = hmac.new(secret.encode("utf-8"), f"{timestamp}.".encode("utf-8") + body, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, s) for s in signatures):
        raise SignatureVerificationError("No signature in Yesly-Signature matches the payload.")


def construct_event(
    payload: Union[str, bytes],
    header: Optional[str],
    secret: str,
    *,
    tolerance: int = DEFAULT_TOLERANCE,
    now: Optional[int] = None,
) -> Event:
    """Verifies a delivery and returns its event. Pass the raw body, before any JSON parsing."""
    verify_signature(payload, header, secret, tolerance=tolerance, now=now)
    return cast(Event, json.loads(payload))


def generate_test_header(payload: str, secret: str, timestamp: Optional[int] = None) -> str:
    """Builds a ``Yesly-Signature`` value, to test your own webhook handler."""
    t = int(time.time()) if timestamp is None else timestamp
    sig = hmac.new(secret.encode("utf-8"), f"{t}.{payload}".encode("utf-8"), hashlib.sha256).hexdigest()
    return f"t={t},v1={sig}"


class Webhook:
    """The same checks as static methods: ``Webhook.construct_event(...)``."""

    DEFAULT_TOLERANCE = DEFAULT_TOLERANCE
    construct_event = staticmethod(construct_event)
    verify_signature = staticmethod(verify_signature)
    generate_test_header = staticmethod(generate_test_header)
