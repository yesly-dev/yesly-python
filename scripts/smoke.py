"""Calls the real API with a test key: one call per resource, then cleans up.

    YESLY_API_KEY=ysk_test_… YESLY_BASE_URL=https://api.dev.yesly.dev/v1 uv run python scripts/smoke.py
"""

import datetime
import itertools
import time

import yesly

client = yesly.Yesly()
assert client.mode == "test", "Use a ysk_test_ key."

tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
external_id = f"SDK-PY-{int(time.time() * 1000)}"


def step(name, value=""):
    print(f"ok  {name}: {value}")


step("balance.retrieve", client.balance.retrieve()["object"])
types = client.appointment_types.list()
step("appointment_types.list", ",".join(t["id"] for t in types.data))
step("locations.list", len(client.locations.list().data))

apt = client.appointments.create(
    external_id=external_id,
    type=types.data[0]["id"],
    customer={"name": "SDK smoke", "phone": "+34600000001"},
    slot={"start": f"{tomorrow}T10:00:00+01:00", "end": f"{tomorrow}T12:00:00+01:00"},
    metadata={"source": "sdk-smoke"},
)
step("appointments.create", f"{apt['id']} {apt['status']}")
step("appointments.retrieve", client.appointments.retrieve(apt["id"])["external_id"])
seen = list(itertools.islice(client.appointments.list(metadata={"source": "sdk-smoke"}, limit=1), 3))
step("appointments.list (auto-paging, limit 1)", len(seen))
step("appointments.update", client.appointments.update(apt["id"], metadata={"note": "updated"})["metadata"]["note"])
step("appointments.cancel", client.appointments.cancel(apt["id"], reason="SDK smoke test")["status"])

we = client.webhook_endpoints.create(url="https://example.com/yesly-sdk-smoke", enabled_events=["appointment.confirmed"])
step("webhook_endpoints.create", we["id"])
step("webhook_endpoints.roll_secret", client.webhook_endpoints.roll_secret(we["id"])["id"])
step("webhook_endpoints.delete", client.webhook_endpoints.delete(we["id"])["deleted"])

events = client.events.list(limit=5)
step("events.list", ",".join(e["type"] for e in events.data))
if events.data:
    step("events.retrieve", client.events.retrieve(events.data[0]["id"])["id"])
step("balance.list_transactions", len(client.balance.list_transactions(limit=5).data))
step("analytics.retrieve_summary", client.analytics.retrieve_summary(range="7d")["appointments"])

try:
    client.appointments.create(external_id=f"{external_id}-bad", customer={"name": "x", "phone": "612"}, slot={"start": f"{tomorrow}T10:00:00+01:00"})
except yesly.InvalidRequestError as e:
    step("validation error", f"{type(e).__name__} {e.status} {e.code} {e.param} {'with request id' if e.request_id else 'NO REQUEST ID'}")
