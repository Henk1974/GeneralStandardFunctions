import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from general_standard_functions.billing.catalog import AddOn, Catalog, Plan, UnknownProductError
from general_standard_functions.billing.stripe import (
    StripeClient,
    StripeError,
    WebhookSignatureError,
    parse_subscription,
    verify_webhook,
)
from general_standard_functions.billing.subscriptions import SubscriptionState, grants_access

CATALOG = Catalog(
    plans=[
        Plan("free", "Gratis", rank=0, limits={"items": 20}),
        Plan("pro", "Pro", rank=1, prices={"month": 149, "year": 1499}, limits={"items": 250}),
        Plan("super", "Super", rank=2, prices={"month": 249, "year": 2499}, limits={"items": None},
             features=frozenset({"groups"})),
    ],
    addons=[AddOn("extra", "Extra", prices={"month": 99, "year": 999}, features=frozenset({"groups"}),
                  plans=frozenset({"pro"}))],
)
NOW = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)


# --- catalogus -----------------------------------------------------------------


def test_limits_per_plan():
    assert CATALOG.entitlements("free").limit("items") == 20
    assert CATALOG.entitlements("pro").limit("items") == 250
    assert CATALOG.entitlements("super").limit("items") is None


def test_addon_only_counts_with_an_allowed_plan():
    assert CATALOG.entitlements("pro", ["extra"]).has("groups")
    assert not CATALOG.entitlements("free", ["extra"]).has("groups")
    assert CATALOG.entitlements("super", ["extra"]).addons == frozenset()  # Super heeft Extra niet nodig
    assert not CATALOG.entitlements("pro", ["onbekend"]).has("groups")


def test_unknown_plan_falls_back_to_default():
    assert CATALOG.entitlements("goud").plan == "free"
    with pytest.raises(UnknownProductError):
        CATALOG.plan("goud")


def test_merge_takes_the_widest_rights():
    gift = CATALOG.entitlements("super")
    paid = CATALOG.entitlements("pro")
    merged = paid.merge(gift, CATALOG.ranks)
    assert merged.plan == "super" and merged.limit("items") is None and merged.has("groups")


def test_prices_in_cents():
    assert CATALOG.price("pro", "year") == 1499 and CATALOG.price("extra", "month") == 99
    with pytest.raises(UnknownProductError):
        CATALOG.price("free", "month")


@pytest.mark.parametrize("plans, addons", [
    ([Plan("free", "a", 0), Plan("free", "b", 1)], []),
    ([Plan("free", "a", 0, prices={"week": 1})], []),
    ([Plan("free", "a", 0)], [AddOn("x", "x", plans=frozenset({"pro"}))]),
])
def test_invalid_catalog_is_refused(plans, addons):
    with pytest.raises(ValueError):
        Catalog(plans, addons)


# --- rechten over tijd -----------------------------------------------------------


@pytest.mark.parametrize("status, expected", [
    ("active", True), ("trialing", True), ("past_due", True),
    ("canceled", False), ("unpaid", False), ("incomplete", False), ("incomplete_expired", False),
])
def test_access_per_status(status, expected):
    state = SubscriptionState("pro", status=status, current_period_end=NOW + timedelta(days=10))
    assert grants_access(state, NOW) is expected


def test_cancelled_at_period_end_keeps_access_until_then():
    state = SubscriptionState("pro", current_period_end=NOW + timedelta(days=1), cancel_at_period_end=True)
    assert grants_access(state, NOW)


def test_missed_notification_does_not_give_access_forever():
    state = SubscriptionState("pro", current_period_end=NOW - timedelta(days=4))
    assert not grants_access(state, NOW)
    assert grants_access(state, NOW, grace=timedelta(days=5))
    assert not grants_access(None, NOW)


# --- webhooks --------------------------------------------------------------------


SECRET = "whsec_test"
BODY = json.dumps({"id": "evt_1", "type": "customer.subscription.updated"}).encode()


def _sign(body=BODY, timestamp=1000, secret=SECRET):
    signature = hmac.new(secret.encode(), str(timestamp).encode() + b"." + body, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


def test_valid_webhook_is_accepted():
    assert verify_webhook(BODY, _sign(), SECRET, now=1010)["type"] == "customer.subscription.updated"


def test_one_of_several_signatures_may_match():
    header = _sign() + ",v1=" + "0" * 64
    assert verify_webhook(BODY, header, SECRET, now=1010)["id"] == "evt_1"


@pytest.mark.parametrize("body, header, secret, now", [
    (BODY, _sign(secret="whsec_ander"), SECRET, 1010),       # verkeerd geheim
    (BODY.replace(b"evt_1", b"evt_2"), _sign(), SECRET, 1010),  # inhoud gewijzigd
    (BODY, _sign(), SECRET, 1000 + 301),                     # te oud
    (BODY, "", SECRET, 1010),                                # geen handtekening
    (BODY, "t=abc,v1=xyz", SECRET, 1010),                    # onleesbaar
    (BODY, _sign(), "", 1010),                               # geen geheim ingesteld
    (b"geen json", _sign(b"geen json"), SECRET, 1010),
])
def test_invalid_webhook_is_refused(body, header, secret, now):
    with pytest.raises(WebhookSignatureError):
        verify_webhook(body, header, secret, now=now)


# --- Stripe-API --------------------------------------------------------------------


def _subscription(**extra):
    data = {
        "id": "sub_1", "customer": "cus_1", "status": "active", "cancel_at_period_end": False,
        "items": {"data": [
            {"id": "si_plan", "price": {"id": "price_pro_m", "recurring": {"interval": "month"}},
             "current_period_end": int((NOW + timedelta(days=20)).timestamp())},
            {"id": "si_extra", "price": {"id": "price_extra_m", "recurring": {"interval": "month"}},
             "current_period_end": int((NOW + timedelta(days=20)).timestamp())},
        ]},
        "metadata": {"user_id": "u1"},
    }
    data.update(extra)
    return data


def test_parse_subscription_reads_items_and_period():
    sub = parse_subscription(_subscription())
    assert sub.price_ids == ["price_pro_m", "price_extra_m"]
    assert sub.current_period_end == NOW + timedelta(days=20) and sub.interval == "month"
    assert sub.metadata == {"user_id": "u1"} and sub.schedule is None


def test_cancel_at_counts_as_cancelled():
    assert parse_subscription(_subscription(cancel_at=123)).cancel_at_period_end


def _client_with(*bodies, status=200):
    responses = []
    for body in bodies:
        response = MagicMock(status_code=status)
        response.json.return_value = body
        responses.append(response)
    patcher = patch("general_standard_functions.billing.stripe.requests.request", side_effect=responses)
    return StripeClient("sk_test_x"), patcher


def test_checkout_sends_server_prices_and_reference():
    client, patcher = _client_with({"url": "https://checkout.stripe.com/c/1"})
    with patcher as request:
        result = client.create_checkout_session(
            ["price_pro_y", "price_extra_y"], "https://app/ok", "https://app/terug", "u1",
            customer_email="a@example.com", metadata={"user_id": "u1"},
        )
    assert result["url"].startswith("https://checkout.stripe.com")
    method, url = request.call_args.args
    data = dict(request.call_args.kwargs["data"])
    assert method == "POST" and url.endswith("/checkout/sessions")
    assert data["mode"] == "subscription" and data["line_items[1][price]"] == "price_extra_y"
    assert data["client_reference_id"] == "u1" and data["subscription_data[metadata][user_id]"] == "u1"
    assert request.call_args.kwargs["headers"]["Authorization"] == "Bearer sk_test_x"


def test_upgrade_replaces_plan_and_removes_addon_only_when_paid():
    client, patcher = _client_with(_subscription())
    with patcher as request:
        client.change_items("sub_1", replace={"si_plan": "price_super_m"}, remove=["si_extra"])
    data = dict(request.call_args.kwargs["data"])
    assert data["items[0][price]"] == "price_super_m" and data["items[1][deleted]"] == "true"
    assert data["payment_behavior"] == "error_if_incomplete"


def test_schedule_keeps_current_items_until_period_end():
    client, patcher = _client_with(
        {"id": "sub_sched_1", "phases": [{"start_date": 500}], "current_phase": {"start_date": 500}},
        {"id": "sub_sched_1"},
    )
    sub = parse_subscription(_subscription())
    with patcher as request:
        assert client.schedule_change_at_period_end(sub, ["price_pro_m"]) == "sub_sched_1"
    create, update = request.call_args_list
    assert dict(create.kwargs["data"]) == {"from_subscription": "sub_1"}
    data = dict(update.kwargs["data"])
    end = str(int(sub.current_period_end.timestamp()))
    assert data["phases[0][items][1][price]"] == "price_extra_m" and data["phases[0][end_date]"] == end
    assert data["phases[1][items][0][price]"] == "price_pro_m" and "phases[1][items][1][price]" not in data
    assert data["end_behavior"] == "release"


def test_stripe_error_is_raised_with_message():
    client, patcher = _client_with({"error": {"message": "Your card was declined."}}, status=402)
    with patcher, pytest.raises(StripeError, match="declined"):
        client.set_cancel_at_period_end("sub_1", True)


def test_client_needs_a_key():
    with pytest.raises(ValueError):
        StripeClient("")
