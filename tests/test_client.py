import re

import httpx
import pytest

import yesly

APT = {"id": "apt_1", "object": "appointment", "external_id": "ORD-48213"}


def test_creates_an_appointment(client, fake):
    fake.queue((201, APT))
    out = client.appointments.create(
        external_id="ORD-48213",
        customer={"name": "Martha", "phone": "+34600000001"},
        slot={"start": "2026-11-13T09:00:00+01:00"},
    )
    assert out == APT
    req = fake.calls[0]
    assert req.method == "POST"
    assert str(req.url) == "https://api.test/v1/appointments"
    assert req.headers["authorization"] == "Bearer ysk_test_123"
    assert req.headers["yesly-version"] == yesly.API_VERSION
    assert req.headers["user-agent"].startswith(f"yesly-python/{yesly.__version__} ")
    assert "idempotency-key" not in req.headers
    # Arguments not given are not sent.
    assert fake.body(0) == {
        "external_id": "ORD-48213",
        "customer": {"name": "Martha", "phone": "+34600000001"},
        "slot": {"start": "2026-11-13T09:00:00+01:00"},
    }


def test_none_is_sent_as_null(client, fake):
    fake.queue((200, {"id": "loc_1"}))
    client.locations.update("bilbao", transfer_phone=None)
    assert fake.body(0) == {"transfer_phone": None}


def test_encodes_ids_and_query(client, fake):
    fake.queue((200, APT), (200, {"object": "list", "url": "/v1/appointments", "has_more": False, "data": []}))
    client.appointments.retrieve("apt/1")
    client.appointments.list(status="no_reply", metadata={"route_id": "BIO-07"}, limit=5, from_="2026-11-13")
    assert fake.calls[0].url.raw_path == b"/v1/appointments/apt%2F1"
    assert fake.calls[1].url.params.multi_items() == [
        ("status", "no_reply"),
        ("from", "2026-11-13"),
        ("metadata[route_id]", "BIO-07"),
        ("limit", "5"),
    ]


def test_booleans_in_query(client, fake):
    fake.queue((200, {"object": "list", "url": "/v1/slots", "has_more": False, "data": []}))
    client.slots.list(available=True)
    assert fake.calls[0].url.params["available"] == "true"


def test_one_idempotency_key_across_retries(client, fake):
    fake.queue((500, {"error": {"type": "api_error", "message": "boom"}}), (503, {}, {"retry-after": "0"}), (200, {"object": "list", "data": []}))
    client.slots.create(slots=[{"start": "2026-11-13T09:00:00+01:00", "type": "delivery"}])
    keys = {c.headers["idempotency-key"] for c in fake.calls}
    assert len(fake.calls) == 3 and len(keys) == 1
    assert re.fullmatch(r"[0-9a-f-]{36}", keys.pop())


def test_uses_the_given_idempotency_key(client, fake):
    fake.queue((200, APT))
    client.appointments.cancel("apt_1", reason="Shop closed", idempotency_key="cancel-apt_1")
    assert fake.calls[0].headers["idempotency-key"] == "cancel-apt_1"
    assert fake.body(0) == {"reason": "Shop closed"}


def test_retries_then_gives_up_on_network_errors(client, fake):
    fake.queue((429, {}, {"retry-after": "0"}), httpx.ConnectError("down"), httpx.ConnectError("down"))
    with pytest.raises(yesly.APIConnectionError):
        client.balance.retrieve()
    assert len(fake.calls) == 3


def test_maps_errors_and_does_not_retry_4xx(client, fake):
    fake.queue((400, {"error": {"type": "invalid_request", "code": "phone_invalid", "param": "customer.phone", "message": "Not E.164", "request_id": "req_1"}}))
    with pytest.raises(yesly.InvalidRequestError) as e:
        client.appointments.create(external_id="x", customer={"phone": "6"}, slot={"start": "2026-11-13T09:00:00+01:00"})
    assert (e.value.status, e.value.code, e.value.param, e.value.request_id) == (400, "phone_invalid", "customer.phone", "req_1")
    assert len(fake.calls) == 1


@pytest.mark.parametrize("status,cls", [(401, yesly.AuthenticationError), (403, yesly.PermissionDeniedError), (404, yesly.NotFoundError), (409, yesly.ConflictError)])
def test_status_classes(client, fake, status, cls):
    fake.queue((status, {"error": {"type": "x", "message": "m"}}))
    with pytest.raises(cls):
        client.events.retrieve("evt_1")


def test_iterating_a_list_walks_every_page(client, fake):
    def page(ids, more):
        return (200, {"object": "list", "url": "/v1/events", "has_more": more, "data": [{"id": i} for i in ids]})

    fake.queue(page(["evt_3", "evt_2"], True), page(["evt_1"], False))
    first = client.events.list(limit=2)
    assert [e["id"] for e in first.data] == ["evt_3", "evt_2"]
    assert [e["id"] for e in first] == ["evt_3", "evt_2", "evt_1"]
    assert fake.calls[1].url.params["starting_after"] == "evt_2"
    assert fake.calls[1].url.params["limit"] == "2"


def test_key_from_environment(monkeypatch):
    monkeypatch.setenv("YESLY_API_KEY", "ysk_live_abc")
    assert yesly.Yesly().mode == "live"
    monkeypatch.delenv("YESLY_API_KEY")
    with pytest.raises(yesly.YeslyError, match="No API key"):
        yesly.Yesly().balance.retrieve()


def test_every_resource_is_attached(client):
    for name in ["appointments", "imports", "slots", "appointment_types", "locations", "webhook_endpoints", "events", "balance", "analytics"]:
        assert getattr(client, name) is not None
    assert callable(client.appointments.import_)
