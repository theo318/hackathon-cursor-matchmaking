"""PayPal for the £1 UNLOCK step (downstream of matching — not signup).

When a match exists and the concierge says "pay £1 to unlock", create an order
here and send the approve link. SANDBOX by default; one env flip to go live.
This is intentionally separate so the signup funnel never depends on PayPal.
"""
import requests
import config

_BASE = ("https://api-m.paypal.com" if config.PAYPAL_ENVIRONMENT == "PRODUCTION"
         else "https://api-m.sandbox.paypal.com")


def _token() -> str:
    r = requests.post(f"{_BASE}/v1/oauth2/token",
                      auth=(config.PAYPAL_CLIENT_ID, config.PAYPAL_CLIENT_SECRET),
                      data={"grant_type": "client_credentials"}, timeout=15)
    r.raise_for_status()
    return r.json()["access_token"]


def create_unlock(match_id: str) -> dict:
    """Returns {order_id, approve_url} for a £1 unlock."""
    tok = _token()
    r = requests.post(
        f"{_BASE}/v2/checkout/orders",
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
        json={"intent": "CAPTURE", "purchase_units": [{
            "reference_id": match_id, "description": "Unlock your match",
            "amount": {"currency_code": config.UNLOCK_CURRENCY, "value": config.UNLOCK_PRICE},
        }]}, timeout=15)
    r.raise_for_status()
    d = r.json()
    approve = next(l["href"] for l in d["links"] if l["rel"] == "approve")
    return {"order_id": d["id"], "approve_url": approve}


def is_paid(order_id: str) -> bool:
    tok = _token()
    r = requests.get(f"{_BASE}/v2/checkout/orders/{order_id}",
                     headers={"Authorization": f"Bearer {tok}"}, timeout=15)
    r.raise_for_status()
    status = r.json().get("status")
    if status == "APPROVED":
        requests.post(f"{_BASE}/v2/checkout/orders/{order_id}/capture",
                      headers={"Authorization": f"Bearer {tok}",
                               "Content-Type": "application/json"}, timeout=15)
        return True
    return status == "COMPLETED"
