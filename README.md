# yesly-python

The official Python library for the Yesly API.

> Status: empty and not published. The package name and the example below match
> what the website shows; change both together if they change.

## Install

```bash
pip install yesly
```

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

## What it must cover

- Every resource in the API reference, with type hints.
- Webhook signature verification (`Yesly-Signature`).
- Retries with idempotency keys, cursor pagination helpers.
- Test and live keys (`ysk_test_…`, `ysk_live_…`).

Types and resources are generated from `yesly-openapi`; hand-written code only
for the parts a spec cannot express.

## Development

To be defined: build, tests and release to PyPI.
