"""Basic usage tests for the ``trace`` decorator: two normal calls and one
error case, verifying that call data lands in ``kodiag.decorators._call_data``.

Traced functions are modeled after the kind of code you'd find in a large
company's backend: order pricing, request auth, and payment processing.
"""

import pytest

import kodiag.decorators as dec
from kodiag import trace


@pytest.fixture
def clean(tmp_path, monkeypatch):
    """Isolate global trace state + output directory for a single test."""
    saved = dict(dec._call_data)
    dec._call_data.clear()
    dec._closed = False
    monkeypatch.chdir(tmp_path)
    yield tmp_path
    dec._call_data.clear()
    dec._call_data.update(saved)
    dec._closed = True


class PaymentDeclinedError(Exception):
    """Raised when a downstream payment processor declines a charge."""


def test_trace_normal_calculate_order_total(clean):
    @trace("order_pricing_trace")
    def calculate_order_total(line_items, tax_rate=0.08, discount_code=None):
        subtotal = sum(item["price"] * item["qty"] for item in line_items)
        if discount_code == "EMPLOYEE10":
            subtotal *= 0.90
        return round(subtotal * (1 + tax_rate), 2)

    cart = [
        {"sku": "USB-C-CABLE", "price": 12.99, "qty": 2},
        {"sku": "LAPTOP-STAND", "price": 45.00, "qty": 1},
    ]

    result = calculate_order_total(cart, discount_code="EMPLOYEE10")

    assert result == round((12.99 * 2 + 45.00) * 0.90 * 1.08, 2)
    calls = dec._call_data["order_pricing_trace.html"]
    assert len(calls) == 1
    assert calls[0]["name"] == "calculate_order_total"
    assert calls[0]["kwargs"] == {"discount_code": "EMPLOYEE10"}
    assert calls[0]["result"] == result
    assert calls[0]["error"] is None


def test_trace_normal_authenticate_api_request(clean):
    @trace("auth_service_trace")
    def authenticate_api_request(api_key, required_scopes):
        granted_scopes = {"read:orders", "write:orders", "read:users"}
        if not required_scopes.issubset(granted_scopes):
            return {"authenticated": True, "authorized": False}
        return {"authenticated": True, "authorized": True}

    result = authenticate_api_request("sk_live_abc123", {"read:orders"})

    assert result == {"authenticated": True, "authorized": True}
    calls = dec._call_data["auth_service_trace.html"]
    assert len(calls) == 1
    assert calls[0]["name"] == "authenticate_api_request"
    assert calls[0]["result"] == {"authenticated": True, "authorized": True}
    assert calls[0]["error"] is None


def test_trace_error_charge_credit_card(clean):
    @trace("payments_service_trace")
    def charge_credit_card(amount_cents, card_token):
        if card_token == "tok_insufficient_funds":
            raise PaymentDeclinedError(f"card {card_token} declined for {amount_cents} cents")
        return {"status": "charged", "amount_cents": amount_cents}

    with pytest.raises(PaymentDeclinedError):
        charge_credit_card(9999, "tok_insufficient_funds")

    calls = dec._call_data["payments_service_trace.html"]
    assert len(calls) == 1
    assert calls[0]["name"] == "charge_credit_card"
    assert calls[0]["result"] is None
    assert "declined" in calls[0]["error"]
