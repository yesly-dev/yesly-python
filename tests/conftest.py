import json
from typing import Any, List

import httpx
import pytest

import yesly


class Fake:
    """An httpx transport that answers from a queue and records each request."""

    def __init__(self) -> None:
        self.answers: List[Any] = []
        self.calls: List[httpx.Request] = []

    def queue(self, *answers: Any) -> "Fake":
        self.answers.extend(answers)
        return self

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        a = self.answers.pop(0)
        if isinstance(a, Exception):
            raise a
        status, body, *rest = a
        headers = rest[0] if rest else {}
        return httpx.Response(status, json=body, headers=headers)

    def body(self, i: int) -> Any:
        return json.loads(self.calls[i].content)


@pytest.fixture
def fake() -> Fake:
    return Fake()


@pytest.fixture
def client(fake: Fake, monkeypatch: pytest.MonkeyPatch) -> yesly.Yesly:
    monkeypatch.setattr("yesly._client._backoff", lambda attempt: 0)
    http = httpx.Client(transport=httpx.MockTransport(fake.handler))
    return yesly.Yesly("ysk_test_123", base_url="https://api.test/v1", http_client=http)
