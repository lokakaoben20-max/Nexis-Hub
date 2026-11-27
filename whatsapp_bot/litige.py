"""Litige d'une demande depuis WhatsApp (étape 7b) : contester la décision de
NexisHub, proposer un accord amiable au prestataire.

Le backend décide de tout : les montants d'une décision ou d'une proposition
sont calculés et figés par le backend (`ledger.decide_dispute`,
`ledger.propose_dispute_settlement`) ; ici, ils sont seulement mis en forme.
Chaque écriture porte le wamid du message qui l'a demandée : un message
rejoué rend la même réponse, sans rien refaire.

Les boutons des notifications du backend portent les mêmes identifiants :
`dispute_contest_c_<n>` (décision envoyée au client) et `doffer_new_<n>`
(proposition refusée ou expirée). Seul le client est sur WhatsApp : la
réponse du prestataire à une proposition reste sur Telegram.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from messages import get_message
from whatsapp_bot import meta
from whatsapp_bot.backend import Refused
from whatsapp_bot.devis import MISSION_ROW, amount_text, reference

CONTEST = "dispute_contest_c_"
CONTEST_PROVIDER = "dispute_contest_p_"  # bouton d'un prestataire : jamais sur WhatsApp
OFFER_NEW = "doffer_new_"
OFFER_SEND = "offer:send:"
OFFER = "offer:"

STEP_CONTEST = "dispute:contest"

OFFER_KINDS = ("redo", "release", "refund", "split")
SPLIT_PERCENTAGES = (25, 50, 75)  # comme sur Telegram (telegram_bot/keyboards.py)
KINSHASA_OFFSET = timedelta(hours=1)
MAX_REASON = 1000

NOT_YOURS = frozenset({"mission_not_found", "not_mission_client", "not_mission_party", "mission_account_missing"})
CHANGED = frozenset(
    {
        "no_decision", "already_contested", "decision_already_executed", "contest_window_closed",
        "already_decided", "not_disputed", "already_settled", "not_paid", "invalid_state",
    }
)  # fmt: skip
_PREFIXES = (CONTEST, CONTEST_PROVIDER, OFFER_NEW, OFFER)


def text(key: str, lang: str, **values) -> str:
    return get_message(key, lang, **values)


def handles(choice: str | None, state: dict) -> bool:
    if state.get("step") == STEP_CONTEST:
        return True
    return bool(choice) and choice.startswith(_PREFIXES)


def _number(value: str) -> int | None:
    return int(value) if value.isdigit() else None


def kinshasa_time(value: str | None) -> str:
    """Échéance lue au backend (UTC, sans fuseau), à l'heure de Kinshasa,
    comme dans les notifications (evenements.kinshasa_time)."""
    try:
        moment = datetime.fromisoformat(value or "")
    except ValueError:
        return "—"
    return f"{moment + KINSHASA_OFFSET:%d/%m/%Y %H:%M}"


def offer_choice(choice: str) -> tuple[str, int | None] | None:
    """`redo`, `release`, `refund` ou `split<pourcentage>` → (type, pourcentage)."""
    if choice in ("redo", "release", "refund"):
        return choice, None
    if choice.startswith("split") and choice[5:].isdigit() and int(choice[5:]) in SPLIT_PERCENTAGES:
        return "split", int(choice[5:])
    return None


class DisputeFlow:
    def __init__(self, conversation) -> None:
        self.conversation = conversation
        self.backend = conversation.backend

    def _menu(self, lang: str, name: str):
        return self.conversation._menu(lang, name)

    # --- Dans « Mes demandes » -----------------------------------------------------

    def cards(self, mission: dict, money: dict, lang: str) -> list:
        """Demande en litige : la décision à contester, la proposition en
        attente, ou « Proposer un accord » (lu au backend, jamais deviné)."""
        mission_id = mission["mission_id"]
        ref = reference(mission_id)
        decisions = money.get("dispute_decisions") or []
        if decisions:
            last = decisions[-1]
            if last.get("state") == "contested":
                return [meta.Text(text("wa_dispute_under_review", lang, reference=ref))]
            if last.get("state") == "pending" and len(decisions) == 1:
                mine, currency = amount_text(last["client_amount"], last["currency"])
                theirs, _ = amount_text(last["provider_amount"], last["currency"])
                body = text(
                    "wa_dispute_decision", lang, reference=ref, mine=mine, theirs=theirs, currency=currency,
                    deadline=kinshasa_time(last.get("execute_after")),
                )  # fmt: skip
                return [meta.Buttons(body=body, buttons=((f"{CONTEST}{mission_id}", text("wa_btn_contest", lang)),))]
            return [meta.Text(text("wa_follow_disputed", lang, reference=ref))]
        pending = [offer for offer in money.get("dispute_offers") or [] if offer.get("state") == "pending"]
        if pending:
            return [meta.Text(text("wa_offer_waiting", lang, reference=ref, deadline=kinshasa_time(pending[-1].get("expires_at"))))]
        return [
            meta.Buttons(
                body=text("wa_follow_disputed", lang, reference=ref) + "\n\n" + text("wa_offer_hint", lang),
                buttons=((f"{OFFER_NEW}{mission_id}", text("wa_btn_offer", lang)),),
            )
        ]

    # --- Appuis et réponses ----------------------------------------------------------

    async def handle(self, message: meta.Incoming, state: dict, lang: str, name: str) -> tuple[list, dict]:
        choice = message.choice if message.kind == meta.CHOICE else None
        if state.get("step") == STEP_CONTEST and not (choice and choice.startswith(_PREFIXES)):
            return await self._on_reason(message, state, lang, name)
        mission_id = None
        try:
            if choice.startswith(CONTEST):
                mission_id = _number(choice[len(CONTEST) :])
                return self._ask_reason(mission_id, lang, name)
            if choice.startswith(OFFER_NEW):
                mission_id = _number(choice[len(OFFER_NEW) :])
                return self._kinds(mission_id, lang, name)
            if choice.startswith(OFFER_SEND):
                mission_part, _, kind = choice[len(OFFER_SEND) :].partition(":")
                mission_id = _number(mission_part)
                return await self._send(message, mission_id, kind, lang, name)
            if choice.startswith(OFFER):
                mission_part, _, kind = choice[len(OFFER) :].partition(":")
                mission_id = _number(mission_part)
                return self._chosen(mission_id, kind, lang, name)
        except Refused as refusal:
            return await self._refused(message, refusal, mission_id, lang, name)
        return self._unknown(lang, name)

    # --- Contester la décision ---------------------------------------------------------

    def _ask_reason(self, mission_id, lang, name):
        if mission_id is None:
            return self._unknown(lang, name)
        prompt = meta.Text(text("wa_dispute_contest_prompt", lang, reference=reference(mission_id)))
        return [prompt], {"step": STEP_CONTEST, "mission_id": mission_id}

    async def _on_reason(self, message, state, lang, name):
        mission_id = state.get("mission_id")
        written = " ".join((message.text or "").split()) if message.kind == meta.TEXT else ""
        if not written:
            refusal = [meta.Text(text("wa_media_refused", lang))] if message.kind == meta.MEDIA else []
            return refusal + [meta.Text(text("wa_dispute_contest_prompt", lang, reference=reference(mission_id)))], state
        try:
            await self.backend.contest_dispute(message.bsuid, message.message_id, mission_id, reason=written[:MAX_REASON])
        except Refused as refusal:
            return await self._refused(message, refusal, mission_id, lang, name)
        return [meta.Text(text("wa_dispute_contested", lang, reference=reference(mission_id))), self._menu(lang, name)], {}

    # --- Proposer un accord ------------------------------------------------------------

    def _kinds(self, mission_id, lang, name):
        if mission_id is None:
            return self._unknown(lang, name)
        rows = tuple((f"{OFFER}{mission_id}:{kind}", text(f"wa_offer_{kind}", lang), text(f"wa_offer_{kind}_hint", lang)) for kind in OFFER_KINDS)
        body = text("wa_offer_choose", lang, reference=reference(mission_id))
        return [meta.Menu(body=body, button=text("wa_list_offer", lang), rows=rows)], {}

    def _chosen(self, mission_id, kind, lang, name):
        if mission_id is None:
            return self._unknown(lang, name)
        if kind == "split":
            rows = tuple(
                (f"{OFFER}{mission_id}:split{percentage}", text("wa_offer_split_pct", lang, percentage=percentage), "")
                for percentage in SPLIT_PERCENTAGES
            )
            body = text("wa_offer_split_choose", lang, reference=reference(mission_id))
            return [meta.Menu(body=body, button=text("wa_list_offer", lang), rows=rows)], {}
        parsed = offer_choice(kind)
        if parsed is None:
            return self._unknown(lang, name)
        offer_kind, percentage = parsed
        card = meta.Buttons(
            body=text(f"wa_offer_confirm_{offer_kind}", lang, reference=reference(mission_id), percentage=percentage),
            buttons=(
                (f"{OFFER_SEND}{mission_id}:{kind}", text("wa_btn_offer_send", lang)),
                (f"{MISSION_ROW}{mission_id}", text("wa_btn_back", lang)),
            ),
        )
        return [card], {}

    async def _send(self, message, mission_id, kind, lang, name):
        parsed = offer_choice(kind)
        if mission_id is None or parsed is None:
            return self._unknown(lang, name)
        offer_kind, percentage = parsed
        answer = await self.backend.propose_settlement(message.bsuid, message.message_id, mission_id, kind=offer_kind, percentage=percentage)
        offers = [offer for offer in (answer.get("money") or {}).get("dispute_offers") or [] if offer.get("state") == "pending"]
        ref = reference(mission_id)
        if not offers:
            return [meta.Text(text("wa_follow_changed", lang)), self._menu(lang, name)], {}
        offer = offers[-1]
        sent = text("wa_offer_sent", lang, reference=ref, deadline=kinshasa_time(offer.get("expires_at")))
        if offer.get("client_amount") is not None:
            mine, currency = amount_text(offer["client_amount"], offer["currency"])
            theirs, _ = amount_text(offer["provider_amount"], offer["currency"])
            sent += "\n\n" + text("wa_offer_amounts", lang, mine=mine, theirs=theirs, currency=currency)
        return [meta.Text(sent), self._menu(lang, name)], {}

    # --- Refus ----------------------------------------------------------------------------

    async def _refused(self, message, refusal: Refused, mission_id, lang, name):
        if refusal.code in NOT_YOURS or mission_id is None or refusal.code == "invalid_offer":
            return self._unknown(lang, name)
        if refusal.code == "offer_pending":
            intro = text("wa_offer_already_pending", lang)
        elif refusal.code in CHANGED or refusal.code == "invalid_reason":
            intro = text("wa_follow_changed", lang)
        else:
            return self.conversation._refused(refusal, lang, {}).as_pair()
        # La demande a bougé entre-temps : on montre où elle en est.
        return await self.conversation.quotes._mission(message, mission_id, lang, name, intro=[meta.Text(intro)])

    def _unknown(self, lang, name):
        return [meta.Text(text("wa_mission_unknown", lang)), self._menu(lang, name)], {}
