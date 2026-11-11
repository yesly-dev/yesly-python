"""Calls the real API with a test key: one call per resource, then cleans up.

    YESLY_API_KEY=ysk_test_… uv run python scripts/smoke.py
"""

import itertools
import time

import yesly

client = yesly.Yesly()
assert client.mode == "test", "Use a ysk_test_ key."

external_id = f"SDK-PY-{int(time.time() * 1000)}"


def step(name, value=""):
    print(f"ok  {name}: {value}")


step("balance.retrieve", client.balance.retrieve()["object"])
agents = client.agents.list()
step("agents.list", ",".join(a["id"] for a in agents.data))
step("senders.list", len(client.senders.list().data))
step("templates.list", len(client.templates.list().data))

contact = client.contacts.create(external_id=external_id, name="SDK smoke", phone="+34600000001", metadata={"source": "sdk-smoke"})
step("contacts.create", contact["id"])
step("contacts.create again (same contact)", client.contacts.create(external_id=external_id, phone="+34600000001")["id"] == contact["id"])
step("contacts.retrieve", client.contacts.retrieve(contact["id"])["external_id"])
step("contacts.update", client.contacts.update(contact["id"], metadata={"note": "updated"})["metadata"]["note"])
seen = list(itertools.islice(client.contacts.list(limit=1), 3))
step("contacts.list (auto-paging, limit 1)", len(seen))
step("contacts.list_memory", len(client.contacts.list_memory(contact["id"]).data))

agent = next((a for a in agents.data if a["status"] == "active"), None)
if agent:
    key = f"{external_id}-cnv"
    cnv = client.conversations.create(agent=agent["id"], contact=contact["id"], channels=[agent["channels"][0]], idempotency_key=key)
    step("conversations.create", f"{cnv['id']} {cnv['status']}")
    again = client.conversations.create(agent=agent["id"], contact=contact["id"], channels=[agent["channels"][0]], idempotency_key=key)
    step("conversations.create again (replayed)", again["id"] == cnv["id"])
    step("conversations.retrieve", client.conversations.retrieve(cnv["id"])["status"])
    step("conversations.list", len(client.conversations.list(contact=contact["id"]).data))
    step("conversations.list_messages", len(client.conversations.list_messages(cnv["id"]).data))
    step("messages.list", len(client.messages.list(conversation=cnv["id"]).data))
else:
    step("conversations.*", "skipped: the account has no active agent")

opt_out = client.opt_outs.create(channel="sms", address="+34600000099")
step("opt_outs.create", opt_out["id"])
step("opt_outs.delete", client.opt_outs.delete(opt_out["id"])["deleted"])

we = client.webhook_endpoints.create(url="https://example.com/yesly-sdk-smoke", enabled_events=["conversation.ended"])
step("webhook_endpoints.create", we["id"])
step("webhook_endpoints.roll_secret", client.webhook_endpoints.roll_secret(we["id"])["id"])
step("webhook_endpoints.delete", client.webhook_endpoints.delete(we["id"])["deleted"])

events = client.events.list(limit=5)
step("events.list", ",".join(e["type"] for e in events.data))
if events.data:
    step("events.retrieve", client.events.retrieve(events.data[0]["id"])["id"])
step("balance.list_transactions", len(client.balance.list_transactions(limit=5).data))
step("analytics.summary", client.analytics.summary(range="7d")["conversations"])

try:
    client.contacts.create(external_id=f"{external_id}-bad", phone="612")
except yesly.InvalidRequestError as e:
    step("validation error", f"{type(e).__name__} {e.status} {e.code} {e.param} {'with request id' if e.request_id else 'NO REQUEST ID'}")
step("contacts.delete", client.contacts.delete(contact["id"])["deleted"])
