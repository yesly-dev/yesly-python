# yesly-python

The official Python library for the Yesly API.

> Status: 0.1.0, not published yet. Covers API version `2026-10-01`.

## Install

```bash
pip install yesly
```

Python 3.9 or later. Depends on `httpx` and `typing-extensions`.

## Usage

```python
import os
from yesly import Yesly

yesly = Yesly(api_key=os.environ["YESLY_API_KEY"])

yesly.appointments.create(
    external_id="ORD-48213",
    type="delivery",
    customer={"name": "Martha", "phone": "+34612345678"},
    slot={"start": "2026-11-13T09:00:00+01:00", "end": "2026-11-13T11:00:00+01:00"},
    metadata={"order_id": "PV-18342", "route_id": "BIO-07"},
)
```

The key defaults to `YESLY_API_KEY`. Every resource of the API reference is an
attribute of the client: `appointments`, `imports`, `slots`,
`appointment_types`, `locations`, `webhook_endpoints`, `events`, `balance` and
`analytics`. Responses are dicts typed with `TypedDict`s (`yesly.types`).
Arguments you do not pass are not sent; `None` is sent as `null`. Where a name
is a Python keyword it ends in `_`: `list(from_=…)`, `appointments.import_(…)`.

## Integration checklist

The usual integration is two calls: create an appointment as soon as it is
booked, and handle the customer's answer on a webhook. These are the points an
integration most often gets wrong; check them before going live. The whole API
reference is also in Markdown, for agents and other tools:
[llms-full.txt](https://yesly.dev/llms-full.txt) (index in
[llms.txt](https://yesly.dev/llms.txt), OpenAPI in
[openapi.yaml](https://yesly.dev/openapi.yaml)).

1. **Set up the appointment types first** (`yesly.appointment_types.create`,
   or in the dashboard). A type sets how the time reads (`time_format`:
   `window`, "between 9:00 and 11:00", or `exact`, "at 17:30"), when the first
   message goes out (`first_contact`) and how far the customer may move it
   (`reschedule`). With a `window` type, `slot.end` is required
   (`slot_end_required`). Send `type` with every appointment when the account
   has more than one type.
2. **Use your own id as `external_id`**: the order, booking or visit number.
   Creating is idempotent by it, so sending the same appointment again returns
   the existing one, and the same id with different data is a `409`
   `external_id_conflict`. To change the time or the customer, update the
   appointment (`yesly.appointments.update`) instead of creating a new one.
3. **Send times with an offset** (`2026-11-13T09:00:00+01:00`) and phones in
   E.164. Yesly contacts Spanish numbers only, and no premium or special-rate
   ones (`phone_not_allowed`).
4. **Handle the answer on a webhook.** Verify the signature over the raw body,
   answer `2xx` within 10 seconds before doing slow work, and skip event ids
   you have already handled: a delivery can arrive more than once. The
   outcomes are `appointment.confirmed`, `appointment.cancelled`,
   `appointment.rescheduled`, `appointment.reschedule_requested` and
   `appointment.no_reply`; each carries your `external_id` and `metadata`.
5. **Build and test with a `ysk_test_` key.** The test phone numbers choose
   the outcome (`+34600000001` confirms on WhatsApp, `+34600000009` never
   answers; the full table is in the reference) and the chain runs in seconds.
   A real number with a test key is refused (`test_number_required`).
6. **Retry only what can succeed.** The library already retries network
   errors, `408`, `429` and `5xx`, with the same idempotency key. A `4xx`
   fails the same way again: fix the request using the error's `code` and
   `param`.
7. **Keep keys on the server.** A read-only key can list and retrieve but not
   write (`api_key_read_only`).

## Webhooks

```python
from yesly import Webhook, SignatureVerificationError

@app.post("/yesly/webhook")
def yesly_webhook():
    try:
        event = Webhook.construct_event(
            request.get_data(),
            request.headers.get("Yesly-Signature", ""),
            os.environ["YESLY_WEBHOOK_SECRET"],
        )
    except SignatureVerificationError:
        return "", 400
    if event["type"] == "appointment.rescheduled":
        appt = event["data"]["appointment"]
    return {"received": True}
```

Pass the raw body. Deliveries more than five minutes old are rejected, and
either signature is accepted during a secret roll. `generate_test_header` signs
a payload to test your handler.
A delivery can arrive more than once, and a captured one stays valid for
those five minutes, so skip events whose `id` you have already handled.

## Lists

A list call returns its first `Page`. Iterating the page walks every page:

```python
page = yesly.events.list(limit=50)
page.data, page.has_more, page.next_page()

for apt in yesly.appointments.list(status="no_reply", metadata={"route_id": "BIO-07"}):
    print(apt["external_id"])
```

## Errors

Failed requests raise a `YeslyError` subclass: `InvalidRequestError` (400,
422), `AuthenticationError` (401), `PermissionDeniedError` (403),
`NotFoundError` (404), `ConflictError` (409), `RateLimitError` (429),
`APIError` (5xx) or `APIConnectionError` (no answer). Each has `status`,
`type`, `code`, `param` and `request_id`.

## Retries, timeouts and idempotency

Network errors, timeouts, 408, 429 and 5xx are retried twice with backoff,
honouring `Retry-After`. POSTs that take an `Idempotency-Key` get one per call,
reused on every retry; pass your own with `idempotency_key=`. Creating an
appointment is idempotent by `external_id` instead.

```python
Yesly(api_key=…, timeout=10.0, max_retries=4)
yesly.appointments.cancel("apt_…", reason="Shop closed", idempotency_key="cancel-ORD-48213")
```

## Test mode

A `ysk_test_` key runs everything in test mode; `yesly.mode` says which. Use
the test phone numbers from the API reference.

## Development

```bash
uv run --group dev pytest
uv run --group dev mypy
```

`src/yesly/_generated/` is generated from the OpenAPI specification. Do not
edit it: change `yesly-openapi`, then, with both repos side by side,

```bash
(cd ../yesly-openapi && npm install)
node ../yesly-openapi/sdk/generate.mjs python .
```

Smoke test against the real API with a test key:

```bash
YESLY_API_KEY=ysk_test_… uv run python scripts/smoke.py
```

## Releasing

Bump `src/yesly/_version.py`, then push a tag `v<version>`.
