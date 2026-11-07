import hashlib
import hmac
import json

import pytest

import yesly
from yesly.webhooks import construct_event, generate_test_header

SECRET = "whsec_test"
BODY = json.dumps({"id": "evt_1", "object": "event", "type": "appointment.confirmed", "data": {"appointment": {"id": "apt_1"}}})
NOW = 1794474252


def sign(secret, t=NOW, payload=BODY):
    return hmac.new(secret.encode(), f"{t}.{payload}".encode(), hashlib.sha256).hexdigest()


def test_valid_signature():
    ev = construct_event(BODY, f"t={NOW},v1={sign(SECRET)}", SECRET, now=NOW)
    assert ev["type"] == "appointment.confirmed"
    assert yesly.Yesly.webhooks.construct_event(BODY.encode(), f"t={NOW},v1={sign(SECRET)}", SECRET, now=NOW)["id"] == "evt_1"


def test_either_signature_during_a_roll():
    assert construct_event(BODY, f"t={NOW},v1={sign('whsec_old')},v1={sign(SECRET)}", SECRET, now=NOW)


def test_rejections():
    h = f"t={NOW},v1={sign(SECRET)}"
    with pytest.raises(yesly.SignatureVerificationError):
        construct_event(BODY + " ", h, SECRET, now=NOW)
    with pytest.raises(yesly.SignatureVerificationError):
        construct_event(BODY, h, "whsec_other", now=NOW)
    with pytest.raises(yesly.SignatureVerificationError, match="tolerance"):
        construct_event(BODY, h, SECRET, now=NOW + 301)
    assert construct_event(BODY, h, SECRET, now=NOW + 301, tolerance=0)
    with pytest.raises(yesly.SignatureVerificationError, match="malformed"):
        construct_event(BODY, "nonsense", SECRET, now=NOW)
    with pytest.raises(yesly.SignatureVerificationError, match="missing"):
        construct_event(BODY, None, SECRET, now=NOW)


def test_generate_test_header():
    assert generate_test_header(BODY, SECRET, NOW) == f"t={NOW},v1={sign(SECRET)}"


def test_webhook_class_as_on_the_website():
    from yesly import SignatureVerificationError, Webhook

    assert Webhook.construct_event(BODY.encode(), f"t={NOW},v1={sign(SECRET)}", SECRET, now=NOW)["id"] == "evt_1"
    with pytest.raises(SignatureVerificationError):
        Webhook.construct_event(BODY, "", SECRET)
