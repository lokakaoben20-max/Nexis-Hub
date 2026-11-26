"""Paiement d'une demande depuis WhatsApp (étape 6) : wallet ou Mobile Money.

Le backend décide de tout : montant, devise et prestataire sont ceux du
devis accepté, relus par le backend ; aucun montant n'est calculé ici, ceux
du backend sont seulement mis en forme. Chaque paiement porte le wamid du
message : un message rejoué ne débite jamais deux fois et ne renvoie jamais
une demande au téléphone (backend/app/main.py, `create_payment_intent`).

Mobile Money : le numéro est celui qui écrit (donné par Meta avec chaque
message signé) ; le client choisit l'opérateur, celui que le numéro laisse
deviner en premier. Seule la confirmation de l'agrégateur paie la mission ;
« Vérifier » relit l'état que le backend connaît (webhook de l'agrégateur et
vérification de secours), sans rien écrire.
"""

from __future__ import annotations

from messages import get_message
from whatsapp_bot import meta
from whatsapp_bot.backend import Refused
from whatsapp_bot.devis import TERMS_REFUSALS, amount_text, reference

PREFIX = "pay:"
PAY_MOBILE = "pay:mm:"
PAY_WALLET = "pay:wallet:"
PAY_OPERATOR = "pay:op:"
PAY_CHECK = "pay:check:"
PAY_LATER = "pay:later"

OPERATORS = {"mpesa": "M-Pesa", "airtel": "Airtel Money", "orange": "Orange Money"}
# Préfixes des opérateurs en RDC (après +243), comme sur Telegram : ils ne
# font que mettre en premier l'opérateur probable, le client choisit.
_OPERATOR_PREFIXES = {
    "81": "mpesa", "82": "mpesa", "83": "mpesa",
    "97": "airtel", "98": "airtel", "99": "airtel",
    "80": "orange", "84": "orange", "85": "orange", "89": "orange",
}  # fmt: skip

WAITING = ("created", "pending")
UNKNOWN_REFUSALS = frozenset(
    {"quote_not_found", "quote_not_accepted", "not_mission_client", "mission_not_found", "intent_not_found", "mission_account_missing"}
)
REFUSAL_TEXTS = {
    "insufficient_balance": "wa_pay_insufficient",
    "payments_paused": "wa_pay_paused",
    "already_paid": "wa_pay_already_paid",
    "invalid_phone": "wa_pay_no_phone",
}


def text(key: str, lang: str, **values) -> str:
    return get_message(key, lang, **values)


def handles(choice: str | None) -> bool:
    return bool(choice) and choice.startswith(PREFIX)


def normalize_phone(raw) -> str | None:
    """Numéro RDC au format +243XXXXXXXXX, ou None s'il n'en est pas un."""
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    if digits.startswith("243"):
        digits = digits[3:]
    elif digits.startswith("0"):
        digits = digits[1:]
    return f"+243{digits}" if len(digits) == 9 else None


def detect_operator(phone: str | None) -> str | None:
    return _OPERATOR_PREFIXES.get(phone[4:6]) if phone else None


def _number(value: str) -> int | None:
    return int(value) if value.isdigit() else None


def _quote_of(choice: str) -> int | None:
    for prefix in (PAY_MOBILE, PAY_WALLET):
        if choice.startswith(prefix):
            return _number(choice[len(prefix) :])
    if choice.startswith(PAY_OPERATOR):
        return _number(choice[len(PAY_OPERATOR) :].partition(":")[0])
    return None


class PaymentFlow:
    def __init__(self, conversation) -> None:
        self.conversation = conversation
        self.backend = conversation.backend

    def _menu(self, lang: str, name: str):
        return self.conversation._menu(lang, name)

    # --- Carte « Payer » ------------------------------------------------------------

    async def pay_card(self, bsuid: str, quote: dict, lang: str) -> meta.Buttons:
        """Choix du paiement d'un devis accepté. Le wallet n'est proposé que
        s'il suffit (le backend revérifie au paiement)."""
        amount, currency = amount_text(quote["amount"], quote["currency"])
        body = text("wa_pay_choose", lang, reference=reference(quote["mission_id"]), amount=amount, currency=currency)
        buttons = [(f"{PAY_MOBILE}{quote['id']}", text("wa_btn_pay_mobile", lang))]
        balance = await self._wallet(bsuid, quote["currency"])
        if balance is not None and balance >= float(quote["amount"]):
            shown, shown_currency = amount_text(balance, quote["currency"])
            body += "\n\n" + text("wa_pay_wallet_line", lang, balance=shown, currency=shown_currency)
            buttons.append((f"{PAY_WALLET}{quote['id']}", text("wa_btn_pay_wallet", lang)))
        buttons.append((PAY_LATER, text("wa_btn_pay_later", lang)))
        return meta.Buttons(body=body, buttons=tuple(buttons))

    async def _wallet(self, bsuid: str, currency: str) -> float | None:
        wallet = (await self.backend.wallet(bsuid)).get("wallet") or {}
        value = wallet.get("wallet_balance_cdf" if currency == "CDF" else "wallet_balance_usd")
        return float(value) if value is not None else None

    # --- Appuis ------------------------------------------------------------------------

    async def handle(self, message: meta.Incoming, lang: str, name: str) -> tuple[list, dict]:
        choice = message.choice
        try:
            if choice == PAY_LATER:
                return [self._menu(lang, name)], {}
            if choice.startswith(PAY_MOBILE):
                return await self._operators(message, _number(choice[len(PAY_MOBILE) :]), lang, name)
            if choice.startswith(PAY_WALLET):
                return await self._pay_wallet(message, _number(choice[len(PAY_WALLET) :]), lang, name)
            if choice.startswith(PAY_OPERATOR):
                quote_part, _, operator = choice[len(PAY_OPERATOR) :].partition(":")
                return await self._pay_mobile(message, _number(quote_part), operator, lang, name)
            if choice.startswith(PAY_CHECK):
                return await self._check(message, _number(choice[len(PAY_CHECK) :]), lang, name)
        except Refused as refusal:
            if refusal.code in TERMS_REFUSALS and _quote_of(choice) is not None:
                # Nouvelles conditions publiées depuis l'acceptation du devis :
                # elles sont acceptées d'abord, puis la demande est remontrée
                # avec sa carte « Payer » (devis.py).
                return await self.conversation.quotes._show_terms(message, _quote_of(choice), lang)
            return self._refused(refusal, lang, name)
        return [meta.Text(text("wa_pay_unknown", lang)), self._menu(lang, name)], {}

    async def _payable_quote(self, bsuid: str, quote_id: int | None) -> dict:
        if quote_id is None:
            raise Refused("quote_not_found", 404)
        quote = (await self.backend.quote(bsuid, quote_id)).get("quote") or {}
        if quote.get("status") != "accepted":
            raise Refused("quote_not_accepted", 409)
        return quote

    @staticmethod
    def _client_phone(message: meta.Incoming) -> str | None:
        """Le numéro qui écrit : Meta le donne avec chaque message signé
        (absent si la personne l'a masqué derrière un nom d'utilisateur)."""
        return normalize_phone(message.phone)

    async def _operators(self, message, quote_id, lang, name):
        quote = await self._payable_quote(message.bsuid, quote_id)
        phone = self._client_phone(message)
        if phone is None:
            return [meta.Text(text("wa_pay_no_phone", lang)), self._menu(lang, name)], {}
        detected = detect_operator(phone)
        amount, currency = amount_text(quote["amount"], quote["currency"])
        buttons = tuple(
            (f"{PAY_OPERATOR}{quote['id']}:{operator}", ("✅ " if operator == detected else "") + label)
            for operator, label in sorted(OPERATORS.items(), key=lambda item: item[0] != detected)
        )
        body = text("wa_pay_operator", lang, amount=amount, currency=currency, phone=phone)
        return [meta.Buttons(body=body, buttons=buttons)], {}

    async def _pay_mobile(self, message, quote_id, operator, lang, name):
        if operator not in OPERATORS:
            raise Refused("quote_not_found", 404)
        quote = await self._payable_quote(message.bsuid, quote_id)
        phone = self._client_phone(message)
        if phone is None:
            return [meta.Text(text("wa_pay_no_phone", lang)), self._menu(lang, name)], {}
        answer = await self.backend.create_payment_intent(
            message.bsuid, message.message_id, quote["mission_id"], quote_id=quote["id"], phone=phone, operator=operator
        )
        return self._status(answer, lang, name)

    async def _check(self, message, intent_id, lang, name):
        if intent_id is None:
            raise Refused("intent_not_found", 404)
        return self._status(await self.backend.payment_intent(message.bsuid, intent_id), lang, name)

    async def _pay_wallet(self, message, quote_id, lang, name):
        quote = await self._payable_quote(message.bsuid, quote_id)
        answer = await self.backend.fund_wallet(message.bsuid, message.message_id, quote["mission_id"], quote_id=quote["id"])
        funding = (answer.get("money") or {}).get("funding") or {}
        amount, currency = amount_text(funding["total"], funding["currency"])
        confirmed = text(
            "wa_pay_confirmed", lang, reference=reference(quote["mission_id"]), ref=funding["reference"], amount=amount, currency=currency
        )
        return [meta.Text(confirmed), self._menu(lang, name)], {}

    # --- Écrans ---------------------------------------------------------------------------

    def _status(self, answer: dict, lang: str, name: str) -> tuple[list, dict]:
        """Écran selon l'état du paiement, comme sur Telegram."""
        intent = answer["intent"]
        mission = reference(intent["mission_id"])
        amount, currency = amount_text(intent["amount"], intent["currency"])
        status = intent["status"]
        if status in WAITING:
            # « created » : l'agrégateur n'a pas encore accusé réception ; on
            # ne sait pas si la demande est arrivée sur le téléphone.
            key = "wa_pay_pending" if status == "pending" else "wa_pay_unconfirmed"
            card = meta.Buttons(
                body=text(key, lang, amount=amount, currency=currency),
                buttons=((f"{PAY_CHECK}{intent['id']}", text("wa_btn_pay_check", lang)),),
            )
            return [card], {}
        if status == "succeeded":
            funding = (answer.get("money") or {}).get("funding") or {}
            paid, paid_currency = amount_text(funding.get("total", intent["amount"]), intent["currency"])
            screen = text("wa_pay_confirmed", lang, reference=mission, ref=funding.get("reference", intent["reference"]), amount=paid, currency=paid_currency)
        elif status in ("overpaid", "mismatch_credited", "mismatch_paid"):
            received = intent.get("received_amount") or intent["amount"]
            shown, shown_currency = amount_text(received, intent.get("received_currency") or intent["currency"])
            screen = text(f"wa_pay_{status}", lang, reference=mission, amount=shown, currency=shown_currency)
        elif status == "mismatch":  # argent reçu, montant différent : l'équipe tranche
            screen = text("wa_pay_mismatch", lang, reference=mission)
        else:  # failed, expired : rien n'a été payé
            screen = text("wa_pay_failed", lang, reference=mission)
        return [meta.Text(screen), self._menu(lang, name)], {}

    def _refused(self, refusal: Refused, lang: str, name: str) -> tuple[list, dict]:
        if refusal.code in REFUSAL_TEXTS:
            return [meta.Text(text(REFUSAL_TEXTS[refusal.code], lang)), self._menu(lang, name)], {}
        if refusal.code in UNKNOWN_REFUSALS:
            return [meta.Text(text("wa_pay_unknown", lang)), self._menu(lang, name)], {}
        return self.conversation._refused(refusal, lang, {}).as_pair()
