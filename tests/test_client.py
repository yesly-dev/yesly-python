import re

import httpx
import pytest

import yesly

CNV = {"id": "cnv_7Qp4Ns2Xk9Lm3D", "object": "conversation", "status": "scheduled"}


def test_creates_a_conversation(client, fake):
    fake.queue((201, CNV))
    out = client.conversations.create(
        agent="agt_8Hd2kQ4mZ1LpXy",
        contact={"external_id": "customer-3391", "phone": "+34600000001", "name": "Marta"},
        channels=["whatsapp", "call"],
        context={"order": "8841"},
    )
    assert out == CNV
    req = fake.calls[0]
    assert req.method == "POST"
    assert str(req.url) == "https://api.test/v1/conversations"
    assert req.headers["authorization"] == "Bearer ysk_test_123"
    assert req.headers["yesly-version"] == yesly.API_VERSION
    assert req.headers["user-agent"].startswith(f"yesly-python/{yesly.__version__} ")
    assert re.fullmatch(r"[0-9a-f-]{36}", req.headers["idempotency-key"])
    # Arguments not given are not sent.
    assert fake.body(0) == {
        "agent": "agt_8Hd2kQ4mZ1LpXy",
        "contact": {"external_id": "customer-3391", "phone": "+34600000001", "name": "Marta"},
        "channels": ["whatsapp", "call"],
        "context": {"order": "8841"},
    }


def test_none_is_sent_as_null(client, fake):
    fake.queue((200, {"id": "ctc_1"}))
    client.contacts.update("ctc_1", name=None, metadata={"note": None})
    assert fake.body(0) == {"name": None, "metadata": {"note": None}}


def test_encodes_ids_and_query(client, fake):
    fake.queue(
        (200, CNV),
        (200, {"object": "list", "url": "/v1/conversations", "has_more": False, "data": []}),
        (200, {"id": "mem_1", "deleted": True}),
    )
    client.conversations.retrieve("cnv/1")
    client.conversations.list(status="no_reply", agent="agt_8Hd2kQ4mZ1LpXy", limit=5, from_="2026-11-13")
    client.contacts.delete_memory("ctc_3Kf9Lq2Wm7Rt4B", "mem/1")
    assert fake.calls[0].url.raw_path == b"/v1/conversations/cnv%2F1"
    assert fake.calls[1].url.params.multi_items() == [
        ("agent", "agt_8Hd2kQ4mZ1LpXy"),
        ("status", "no_reply"),
        ("from", "2026-11-13"),
        ("limit", "5"),
    ]
    assert fake.calls[2].method == "DELETE"
    assert fake.calls[2].url.raw_path == b"/v1/contacts/ctc_3Kf9Lq2Wm7Rt4B/memory/mem%2F1"


def test_booleans_and_dicts_in_query(client, fake):
    fake.queue((200, {}))
    client._request("GET", "/x", query={"flag": True, "metadata": {"k": "v"}})
    assert fake.calls[0].url.params.multi_items() == [("flag", "true"), ("metadata[k]", "v")]


def test_one_idempotency_key_across_retries(client, fake):
    fake.queue((500, {"error": {"type": "api_error", "message": "boom"}}), (503, {}, {"retry-after": "0"}), (200, {"id": "ctc_1"}))
    client.contacts.create(external_id="customer-3391", phone="+34600000001")
    keys = {c.headers["idempotency-key"] for c in fake.calls}
    assert len(fake.calls) == 3 and len(keys) == 1
    assert re.fullmatch(r"[0-9a-f-]{36}", keys.pop())


def test_uses_the_given_idempotency_key(client, fake):
    fake.queue((200, CNV))
    client.conversations.cancel("cnv_7Qp4Ns2Xk9Lm3D", idempotency_key="cancel-order-8841")
    assert fake.calls[0].url.raw_path == b"/v1/conversations/cnv_7Qp4Ns2Xk9Lm3D/cancel"
    assert fake.calls[0].headers["idempotency-key"] == "cancel-order-8841"


def test_retries_then_gives_up_on_network_errors(client, fake):
    fake.queue((429, {}, {"retry-after": "0"}), httpx.ConnectError("down"), httpx.ConnectError("down"))
    with pytest.raises(yesly.APIConnectionError):
        client.balance.retrieve()
    assert len(fake.calls) == 3


def test_maps_errors_and_does_not_retry_4xx(client, fake):
    fake.queue((422, {"error": {"type": "invalid_request", "code": "phone_invalid", "param": "contact.phone", "message": "Not E.164", "request_id": "req_1"}}))
    with pytest.raises(yesly.InvalidRequestError) as e:
        client.conversations.create(agent="agt_8Hd2kQ4mZ1LpXy", contact={"phone": "6"}, channels=["call"])
    assert (e.value.status, e.value.code, e.value.param, e.value.request_id) == (422, "phone_invalid", "contact.phone", "req_1")
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


def test_turns_without_id_come_in_one_page(client, fake):
    turn = {"object": "turn", "role": "contact", "channel": "whatsapp", "message": "msg_1", "text": "Vale", "at": "2026-12-01T10:03:41+01:00"}
    fake.queue((200, {"object": "list", "url": "/v1/conversations/cnv_1/messages", "has_more": False, "data": [turn, turn]}))
    assert [t["text"] for t in client.conversations.list_messages("cnv_1")] == ["Vale", "Vale"]
    assert len(fake.calls) == 1


def test_next_page_needs_an_item_id(client, fake):
    fake.queue((200, {"object": "list", "has_more": True, "data": [{"object": "turn"}]}))
    page = client.conversations.list_messages("cnv_1")
    with pytest.raises(StopIteration):
        page.next_page()


def test_key_from_environment(monkeypatch):
    monkeypatch.setenv("YESLY_API_KEY", "ysk_live_abc")
    assert yesly.Yesly().mode == "live"
    monkeypatch.delenv("YESLY_API_KEY")
    with pytest.raises(yesly.YeslyError, match="No API key"):
        yesly.Yesly().balance.retrieve()


def test_every_resource_is_attached(client):
    for name in ["agents", "senders", "contacts", "conversations", "messages", "templates", "opt_outs", "analytics", "balance", "webhook_endpoints", "events"]:
        assert getattr(client, name) is not None
    assert callable(client.contacts.list_memory)


def test_base_url_must_be_https_except_for_localhost():
    with pytest.raises(yesly.YeslyError, match="must use https"):
        yesly.Yesly("ysk_test_123", base_url="http://api.yesly.dev/v1")
    for base_url in ("http://localhost:4010", "http://127.0.0.1:4010/v1", "http://[::1]:4010"):
        assert yesly.Yesly("ysk_test_123", base_url=base_url).base_url == base_url
