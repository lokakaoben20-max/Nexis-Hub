"""Agrégateur de paiement Mobile Money (CONCEPTION_MOBILE_MONEY.md).

Le reste du backend ne parle qu'à `get_gateway()` : demander un encaissement
ou un versement, en lire le statut, vérifier un webhook. Une implémentation
par agrégateur ; SerdiPay (choisi par Ben le 2026-11-19, FlexPaie en
secours) s'écrira ici à l'étape 5, une fois le contrat signé et la
documentation reçue.

Contrat que toute implémentation doit tenir :

- Chaque demande porte **notre** référence (`intent.reference`,
  `payout.reference`), créée et enregistrée en base avant tout appel.
  L'agrégateur doit refuser un second ordre portant une référence déjà
  utilisée (ou renvoyer la transaction existante) : c'est ce qui rend sûr le
  renvoi d'un versement dont on n'a jamais eu de réponse.
- Le statut se relit par notre référence. `NOT_FOUND` veut dire que
  l'agrégateur ne connaît aucune transaction portant cette référence : la
  demande ne lui est jamais parvenue. Ce n'est jamais un échec de paiement.
- `GatewayUnavailable` : pas de réponse, on ne sait rien. L'appelant ne
  conclut rien et relira plus tard.
- Un statut que l'implémentation ne sait pas traduire lève une exception,
  jamais un `FAILED` par défaut.
- `SUCCEEDED` porte toujours la référence de l'agrégateur, le montant et la
  devise réellement encaissés ou versés.

`SimulationGateway` sert au développement local et aux tests : elle confirme
tout immédiatement. Elle est refusée en production (`APP_ENV=production`).
"""

import os
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from backend.app.ledger import CENT, to_money

PENDING, SUCCEEDED, FAILED = "pending", "succeeded", "failed"
# Aucune transaction avec notre référence chez l'agrégateur (voir ci-dessus).
NOT_FOUND = "not_found"


@dataclass
class GatewayResult:
    status: str  # pending | succeeded | failed | not_found
    reference: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    fee: Decimal | None = None
    reason: str | None = None


@dataclass
class WebhookNotice:
    """Ce qu'un webhook authentifié désigne : notre référence (de préférence)
    et/ou celle de l'agrégateur. Le webhook ne dit rien d'autre qui compte :
    le statut est toujours relu chez l'agrégateur."""

    reference: str | None = None
    gateway_reference: str | None = None


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

    def verify_webhook(self, headers, body: bytes) -> WebhookNotice:
        raise InvalidWebhook("la simulation n'envoie pas de webhook")


GATEWAYS = {"simulation": SimulationGateway}


def get_gateway():
    name = os.getenv("PAYMENT_GATEWAY", "simulation")
    if name == "simulation" and os.getenv("APP_ENV") == "production":
        raise RuntimeError("Paiement simulé refusé en production (PAYMENT_GATEWAY)")
    if name not in GATEWAYS:
        raise RuntimeError(f"Agrégateur inconnu : {name}")
    return GATEWAYS[name]()
