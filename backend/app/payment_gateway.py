"""Agrégateur de paiement Mobile Money (CONCEPTION_MOBILE_MONEY.md).

Le reste du backend ne parle qu'à `get_gateway()` : demander un encaissement
ou un versement, en lire le statut, vérifier un webhook. Une implémentation
par agrégateur ; FlexPaie (choisi par Ben) s'écrira ici à l'étape 5, une fois
le KYC validé et la signature des webhooks confirmée par écrit.

`SimulationGateway` sert au développement local et aux tests : elle confirme
tout immédiatement. Elle est refusée en production (`APP_ENV=production`).
"""

import os
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from backend.app.ledger import CENT, to_money

PENDING, SUCCEEDED, FAILED = "pending", "succeeded", "failed"


@dataclass
class GatewayResult:
    status: str  # pending | succeeded | failed
    reference: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    fee: Decimal | None = None
    reason: str | None = None


class GatewayUnavailable(Exception):
    """L'agrégateur n'a pas répondu : on ne sait rien, on ne bouge rien."""


class InvalidWebhook(Exception):
    """Webhook non authentifié : ignoré."""


def collection_fee_rate() -> Decimal:
    # Frais d'encaissement attendus (FlexPaie : 2,5 %), à la charge de Nexis
    # Hub. Réglage, pas valeur en dur (décision de Ben : « on verra ensuite »).
    return Decimal(os.getenv("COLLECTION_FEE_RATE", "0.025"))


class SimulationGateway:
    name = "simulation"

    def request_collection(self, intent) -> GatewayResult:
        return self.collection_status(intent)

    def collection_status(self, intent) -> GatewayResult:
        amount = to_money(intent.amount)
        fee = (amount * collection_fee_rate()).quantize(CENT, rounding=ROUND_HALF_UP)
        return GatewayResult(SUCCEEDED, f"SIM-PAY-{intent.id:06d}", amount, intent.currency, fee)

    def request_payout(self, payout) -> GatewayResult:
        return self.payout_status(payout)

    def payout_status(self, payout) -> GatewayResult:
        return GatewayResult(SUCCEEDED, f"SIM-OUT-{payout.id:06d}", to_money(payout.amount), payout.currency)

    def verify_webhook(self, headers, body: bytes) -> str:
        raise InvalidWebhook("la simulation n'envoie pas de webhook")


GATEWAYS = {"simulation": SimulationGateway}


def get_gateway():
    name = os.getenv("PAYMENT_GATEWAY", "simulation")
    if name == "simulation" and os.getenv("APP_ENV") == "production":
        raise RuntimeError("Paiement simulé refusé en production (PAYMENT_GATEWAY)")
    if name not in GATEWAYS:
        raise RuntimeError(f"Agrégateur inconnu : {name}")
    return GATEWAYS[name]()
