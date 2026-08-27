from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CheckoutSession:
    """What a provider returns when we ask it to collect money from the student."""
    reference: str          # provider-side id, stored on wallet_transactions.kpay_reference
    checkout_url: str       # where we send the student to actually pay
    amount_cents: int
    currency: str


@dataclass
class WebhookEvent:
    """Normalized shape every provider's webhook gets parsed into."""
    reference: str
    status: str              # "succeeded" | "failed" | "pending"
    amount_cents: int
    currency: str
    metadata: dict


class PaymentProvider(ABC):
    """
    Everything the rest of the app needs from a payment provider. Route
    handlers and the wallet logic only ever talk to this interface — swap
    KpayProvider for another implementation without touching anything else.
    """

    @abstractmethod
    def create_checkout(
        self, *, amount_cents: int, currency: str, student_id: str,
        purpose: str, metadata: dict,
    ) -> CheckoutSession:
        """Start a payment (e.g. wallet top-up) and get back a URL to send the student to."""

    @abstractmethod
    def parse_webhook(self, *, payload: bytes, signature_header: str) -> WebhookEvent:
        """Verify + normalize an inbound webhook call from the provider."""

    @abstractmethod
    def refund(self, *, reference: str, amount_cents: int | None = None) -> bool:
        """Refund a previous charge, in full or in part."""
