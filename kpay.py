"""
Kpay adapter.

"Kpay" isn't one single company — there are several unrelated real
products by that name (a pan-African mobile-money gateway, Myanmar's
KBZPay mobile wallet, KPay Group's general payment gateway, etc). This
adapter targets **KPay Group** (go.kpay-group.com), since it's a general
Stripe-like gateway — hosted checkout, payment-intent objects with
id/amount/currency/status/metaData, webhooks, refunds — which is the
closest structural fit for a global platform charging students in many
currencies.

IMPORTANT: the exact endpoint paths, auth header format, and webhook
signature scheme below are reasonable assumptions based on KPay Group's
public marketing/docs pages, not a verified private API spec. Before
going live:
  1. Confirm the real base path and auth scheme in your KPay merchant
     dashboard docs.
  2. Confirm the webhook signature header name and algorithm.
  3. Update KPAY_ENDPOINTS / _headers() / parse_webhook() below —
     everything else in the app talks to PaymentProvider, not to this
     file directly, so this is the only place that needs to change.

Design note: Kpay doesn't appear to offer card-issuing the way Stripe
Issuing does, so the "single-use virtual card per application" idea from
the original spec is replaced here with a simpler, equally safe pattern:
students top up a wallet balance via Kpay checkout, and each application
fee is a ledger debit from that balance — gated by the student's explicit
per-charge confirmation (see routers/wallet.py). No charge ever fires
without that confirmation either way.
"""
import hashlib
import hmac
import json

import httpx

from app.config import settings
from app.payments.base import PaymentProvider, CheckoutSession, WebhookEvent

KPAY_ENDPOINTS = {
    "create_intent": "/v1/payment_intents",
    "refund": "/v1/refunds",
}


class KpayProvider(PaymentProvider):
    def __init__(self):
        self.base_url = settings.kpay_base_url.rstrip("/")
        self.api_key = settings.kpay_api_key
        self.webhook_secret = settings.kpay_webhook_secret

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def create_checkout(
        self, *, amount_cents: int, currency: str, student_id: str,
        purpose: str, metadata: dict,
    ) -> CheckoutSession:
        body = {
            "amount": amount_cents,
            "currency": currency,
            "metaData": {"student_id": student_id, "purpose": purpose, **metadata},
        }
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                f"{self.base_url}{KPAY_ENDPOINTS['create_intent']}",
                headers=self._headers(),
                json=body,
            )
        resp.raise_for_status()
        data = resp.json()
        # Assumption: response includes {"id": "PI_...", "checkoutUrl": "..."}
        # matching the hosted-checkout flow described in KPay Group's docs.
        return CheckoutSession(
            reference=data["id"],
            checkout_url=data.get("checkoutUrl") or data.get("checkout_url", ""),
            amount_cents=amount_cents,
            currency=currency,
        )

    def parse_webhook(self, *, payload: bytes, signature_header: str) -> WebhookEvent:
        expected_sig = hmac.new(
            self.webhook_secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected_sig, signature_header or ""):
            raise ValueError("Invalid Kpay webhook signature")

        event = json.loads(payload)
        intent = event.get("data", event)  # tolerate either a raw intent or an {event, data} envelope
        return WebhookEvent(
            reference=intent["id"],
            status=intent["status"],  # e.g. "succeeded" | "failed" | "pending"
            amount_cents=intent["amount"],
            currency=intent["currency"],
            metadata=intent.get("metaData", {}),
        )

    def refund(self, *, reference: str, amount_cents: int | None = None) -> bool:
        body = {"payment_intent_id": reference}
        if amount_cents is not None:
            body["amount"] = amount_cents
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                f"{self.base_url}{KPAY_ENDPOINTS['refund']}",
                headers=self._headers(),
                json=body,
            )
        resp.raise_for_status()
        return resp.json().get("status") == "succeeded"


def get_payment_provider() -> PaymentProvider:
    return KpayProvider()
