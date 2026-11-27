"""Suivi d'une demande payée depuis WhatsApp (étape 7) : arrivée du
prestataire, fin du travail, problème, avis, et « Mon solde ».

Le backend décide de tout : qui peut confirmer, quand l'argent est libéré
(une seule fois, phase unique du registre), quand il est gelé (litige). Chaque
écriture porte le wamid du message qui l'a demandée : un message rejoué rend
la même réponse, sans rien refaire. Aucun montant n'est calculé ici.

Les boutons des notifications du backend (`evenements.presence_question_buttons`,
`evenements.completion_buttons`) portent les mêmes identifiants que ceux de
« Mes demandes » : `presence_yes_<n>`, `presence_notyet_<n>`,
`presence_wrong_<n>`, `client_confirm_done_<n>`, `client_report_issue_<n>`.

Deux appuis demandent une confirmation, parce qu'ils ne se défont pas :
« Ce n'est pas lui » (gèle l'argent et bloque le prestataire) et « Confirmer
la fin » (paie le prestataire).
"""

from __future__ import annotations

from messages import get_message
from whatsapp_bot import meta
from whatsapp_bot.backend import Refused
from whatsapp_bot.devis import MISSION_ROW, amount_text, reference

PRESENCE_YES = "presence_yes_"
PRESENCE_NOT_YET = "presence_notyet_"
PRESENCE_WRONG = "presence_wrong_"
PRESENCE_WRONG_OK = "presence_wrongok_"
DONE = "client_confirm_done_"
DONE_OK = "client_done_ok_"
ISSUE = "client_report_issue_"
ISSUE_REASON = "issue:"
RATE = "rate:"
RATE_STAR = "rate:star:"
RATE_SKIP = "rate:skip:"

STEP_ISSUE = "follow:issue"
STEP_COMMENT = "follow:comment"

ISSUE_REASONS = ("bad_work", "unfinished", "no_show", "damage", "other")
MAX_ISSUE_TEXT = 800
MAX_COMMENT = 500
HISTORY_LINES = 5

NOT_YOURS = frozenset({"mission_not_found", "not_mission_client", "mission_account_missing", "no_provider"})
_PREFIXES = (
    PRESENCE_YES, PRESENCE_NOT_YET, PRESENCE_WRONG_OK, PRESENCE_WRONG, DONE_OK, DONE, ISSUE, ISSUE_REASON, RATE,
)  # fmt: skip


def text(key: str, lang: str, **values) -> str:
    return get_message(key, lang, **values)


def handles(choice: str | None, state: dict) -> bool:
    if state.get("step") in (STEP_ISSUE, STEP_COMMENT):
        return True
    return bool(choice) and choice.startswith(_PREFIXES)


def _number(value: str) -> int | None:
    return int(value) if value.isdigit() else None


class FollowFlow:
    def __init__(self, conversation) -> None:
        self.conversation = conversation
        self.backend = conversation.backend

    def _menu(self, lang: str, name: str):
        return self.conversation._menu(lang, name)

    # --- Dans « Mes demandes » -----------------------------------------------------

    async def cards(self, bsuid: str, mission: dict, review: dict | None, lang: str, money: dict | None = None) -> list:
        """Ce que le client peut faire maintenant, selon l'état de sa
        demande (lu au backend, jamais deviné)."""
        mission_id = mission["mission_id"]
        status = mission.get("status")
        if status == "confirmed" and mission.get("payment_status") == "paid_escrow":
            presence = (await self.backend.presence(bsuid, mission_id)).get("presence") or {}
            return self._presence_cards(mission_id, presence, lang)
        if status == "in_progress":
            return [meta.Buttons(body=text("wa_follow_in_progress", lang), buttons=((f"{ISSUE}{mission_id}", text("wa_btn_issue", lang)),))]
        if status == "awaiting_confirmation":
            return [self._finished_card(mission_id, lang)]
        if status == "completed" and review is None and mission.get("payment_status") == "released":
            return [meta.Buttons(body=text("wa_rate_offer", lang), buttons=((f"{RATE}{mission_id}", text("wa_btn_rate", lang)),))]
        if status == "disputed":
            # Décision à contester, accord à proposer (litige.py).
            return self.conversation.disputes.cards(mission, money or {}, lang)
        return []

    def _presence_cards(self, mission_id: int, presence: dict, lang: str) -> list:
        code = presence.get("code")
        if not code:
            return []
        body = text("wa_presence_code", lang, code=code)
        if not presence.get("arrival_declared"):
            return [meta.Text(body + "\n\n" + text("wa_presence_wait", lang))]
        body += "\n\n" + text("wa_presence_question", lang)
        buttons = (
            (f"{PRESENCE_YES}{mission_id}", text("wa_btn_presence_yes", lang)),
            (f"{PRESENCE_NOT_YET}{mission_id}", text("wa_btn_presence_not_yet", lang)),
            (f"{PRESENCE_WRONG}{mission_id}", text("wa_btn_presence_wrong", lang)),
        )
        return [meta.Buttons(body=body, buttons=buttons)]

    def _finished_card(self, mission_id: int, lang: str) -> meta.Buttons:
        return meta.Buttons(
            body=text("wa_follow_finished", lang, reference=reference(mission_id)),
            buttons=((f"{DONE}{mission_id}", text("wa_btn_done", lang)), (f"{ISSUE}{mission_id}", text("wa_btn_issue", lang))),
        )

    # --- Appuis et réponses ----------------------------------------------------------

    async def handle(self, message: meta.Incoming, state: dict, lang: str, name: str) -> tuple[list, dict]:
        choice = message.choice if message.kind == meta.CHOICE else None
        step = state.get("step")
        if step in (STEP_ISSUE, STEP_COMMENT) and not (choice and choice.startswith(_PREFIXES)):
            return await self._on_step(message, state, lang, name, choice)
        mission_id = None
        try:
            if choice.startswith(PRESENCE_YES):
                mission_id = _number(choice[len(PRESENCE_YES) :])
                return await self._presence_yes(message, mission_id, lang, name)
            if choice.startswith(PRESENCE_NOT_YET):
                mission_id = _number(choice[len(PRESENCE_NOT_YET) :])
                return await self._presence_not_yet(message, mission_id, lang, name)
            if choice.startswith(PRESENCE_WRONG_OK):
                mission_id = _number(choice[len(PRESENCE_WRONG_OK) :])
                return await self._presence_wrong(message, mission_id, lang, name)
            if choice.startswith(PRESENCE_WRONG):
                mission_id = _number(choice[len(PRESENCE_WRONG) :])
                return self._ask_wrong(mission_id, lang, name)
            if choice.startswith(DONE_OK):
                mission_id = _number(choice[len(DONE_OK) :])
                return await self._done(message, mission_id, lang, name)
            if choice.startswith(DONE):
                mission_id = _number(choice[len(DONE) :])
                return self._ask_done(mission_id, lang, name)
            if choice.startswith(ISSUE_REASON):
                mission_part, _, reason = choice[len(ISSUE_REASON) :].partition(":")
                mission_id = _number(mission_part)
                return self._ask_issue_details(mission_id, reason, lang, name)
            if choice.startswith(ISSUE):
                mission_id = _number(choice[len(ISSUE) :])
                return self._issue_reasons(mission_id, lang, name)
            if choice.startswith(RATE_SKIP):
                mission_id = _number(choice[len(RATE_SKIP) :])
                if step != STEP_COMMENT or state.get("mission_id") != mission_id:
                    # Ancien bouton : la note choisie n'est plus connue.
                    return self._stars(mission_id, lang, name)
                return await self._review(message, mission_id, state.get("rating"), None, lang, name)
            if choice.startswith(RATE_STAR):
                mission_part, _, rating = choice[len(RATE_STAR) :].partition(":")
                mission_id = _number(mission_part)
                return self._ask_comment(mission_id, _number(rating), lang, name)
            if choice.startswith(RATE):
                mission_id = _number(choice[len(RATE) :])
                return self._stars(mission_id, lang, name)
        except Refused as refusal:
            return await self._refused(message, refusal, mission_id, lang, name)
        return self._unknown(lang, name)

    async def _on_step(self, message, state, lang, name, choice):
        mission_id = state.get("mission_id")
        if message.kind != meta.TEXT or not (message.text or "").strip():
            refusal = [meta.Text(text("wa_media_refused", lang))] if message.kind == meta.MEDIA else []
            return refusal + [self._step_prompt(state["step"], mission_id, lang)], state
        written = " ".join(message.text.split())
        try:
            if state["step"] == STEP_ISSUE:
                return await self._issue(message, mission_id, state.get("reason"), written, lang, name)
            return await self._review(message, mission_id, state.get("rating"), written[:MAX_COMMENT], lang, name)
        except Refused as refusal:
            return await self._refused(message, refusal, mission_id, lang, name)

    def _step_prompt(self, step: str, mission_id: int, lang: str):
        if step == STEP_ISSUE:
            return meta.Text(text("wa_issue_details", lang, reference=reference(mission_id)))
        return meta.Buttons(body=text("wa_rate_comment", lang), buttons=((f"{RATE_SKIP}{mission_id}", text("wa_btn_rate_skip", lang)),))

    # --- Arrivée -----------------------------------------------------------------------

    async def _presence_yes(self, message, mission_id, lang, name):
        if mission_id is None:
            return self._unknown(lang, name)
        await self.backend.presence_confirm(message.bsuid, message.message_id, mission_id)
        return [meta.Text(text("wa_presence_confirmed", lang, reference=reference(mission_id))), self._menu(lang, name)], {}

    async def _presence_not_yet(self, message, mission_id, lang, name):
        if mission_id is None:
            return self._unknown(lang, name)
        await self.backend.presence_not_yet(message.bsuid, message.message_id, mission_id)
        return [meta.Text(text("wa_presence_not_yet", lang)), self._menu(lang, name)], {}

    def _ask_wrong(self, mission_id, lang, name):
        if mission_id is None:
            return self._unknown(lang, name)
        card = meta.Buttons(
            body=text("wa_presence_wrong_confirm", lang, reference=reference(mission_id)),
            buttons=(
                (f"{PRESENCE_WRONG_OK}{mission_id}", text("wa_btn_presence_wrong_ok", lang)),
                (f"{MISSION_ROW}{mission_id}", text("wa_btn_back", lang)),
            ),
        )
        return [card], {}

    async def _presence_wrong(self, message, mission_id, lang, name):
        if mission_id is None:
            return self._unknown(lang, name)
        await self.backend.presence_wrong_person(message.bsuid, message.message_id, mission_id)
        return [meta.Text(text("wa_presence_wrong_done", lang, reference=reference(mission_id))), self._menu(lang, name)], {}

    # --- Fin du travail ----------------------------------------------------------------

    def _ask_done(self, mission_id, lang, name):
        if mission_id is None:
            return self._unknown(lang, name)
        card = meta.Buttons(
            body=text("wa_done_confirm", lang, reference=reference(mission_id)),
            buttons=((f"{DONE_OK}{mission_id}", text("wa_btn_done_ok", lang)), (f"{MISSION_ROW}{mission_id}", text("wa_btn_back", lang))),
        )
        return [card], {}

    async def _done(self, message, mission_id, lang, name):
        if mission_id is None:
            return self._unknown(lang, name)
        answer = await self.backend.confirm_completion(message.bsuid, message.message_id, mission_id)
        released = meta.Text(text("wa_done_released", lang, reference=reference(mission_id)))
        if (answer.get("mission") or {}).get("status") != "completed":
            return [released, self._menu(lang, name)], {}
        messages, state = self._stars(mission_id, lang, name)
        return [released, *messages], state

    # --- Problème ------------------------------------------------------------------------

    def _issue_reasons(self, mission_id, lang, name):
        if mission_id is None:
            return self._unknown(lang, name)
        rows = tuple(
            (f"{ISSUE_REASON}{mission_id}:{reason}", text(f"wa_issue_reason_{reason}", lang), "")
            for reason in ISSUE_REASONS
        )
        menu = meta.Menu(body=text("wa_issue_choose", lang, reference=reference(mission_id)), button=text("wa_list_issue", lang), rows=rows)
        return [menu], {}

    def _ask_issue_details(self, mission_id, reason, lang, name):
        if mission_id is None or reason not in ISSUE_REASONS:
            return self._unknown(lang, name)
        state = {"step": STEP_ISSUE, "mission_id": mission_id, "reason": reason}
        return [self._step_prompt(STEP_ISSUE, mission_id, lang)], state

    async def _issue(self, message, mission_id, reason, written, lang, name):
        if reason not in ISSUE_REASONS:
            return self._issue_reasons(mission_id, lang, name)
        # Le motif est lu par l'équipe : en français, suivi des mots du client.
        label = text(f"wa_issue_reason_{reason}", "fr")
        await self.backend.open_dispute(message.bsuid, message.message_id, mission_id, reason=f"{label} : {written[:MAX_ISSUE_TEXT]}")
        return [meta.Text(text("wa_issue_opened", lang, reference=reference(mission_id))), self._menu(lang, name)], {}

    # --- Avis ------------------------------------------------------------------------------

    def _stars(self, mission_id, lang, name):
        if mission_id is None:
            return self._unknown(lang, name)
        rows = tuple(
            (f"{RATE_STAR}{mission_id}:{rating}", "⭐" * rating, text(f"wa_rate_{rating}", lang)) for rating in range(5, 0, -1)
        )
        menu = meta.Menu(body=text("wa_rate_choose", lang, reference=reference(mission_id)), button=text("wa_list_rate", lang), rows=rows)
        return [menu], {}

    def _ask_comment(self, mission_id, rating, lang, name):
        if mission_id is None or rating not in range(1, 6):
            return self._unknown(lang, name)
        state = {"step": STEP_COMMENT, "mission_id": mission_id, "rating": rating}
        return [self._step_prompt(STEP_COMMENT, mission_id, lang)], state

    async def _review(self, message, mission_id, rating, comment, lang, name):
        if rating not in range(1, 6):
            return self._stars(mission_id, lang, name)
        await self.backend.review(message.bsuid, message.message_id, mission_id, rating=rating, comment=comment)
        return [meta.Text(text("wa_rate_thanks", lang)), self._menu(lang, name)], {}

    # --- « Mon solde » ---------------------------------------------------------------------

    async def wallet(self, message: meta.Incoming, lang: str, name: str) -> tuple[list, dict]:
        wallet = (await self.backend.wallet(message.bsuid)).get("wallet") or {}
        entries = (await self.backend.wallet_history(message.bsuid, limit=HISTORY_LINES)).get("entries") or []
        usd, _ = amount_text(wallet.get("wallet_balance_usd") or 0, "USD")
        cdf, _ = amount_text(wallet.get("wallet_balance_cdf") or 0, "CDF")
        body = text("wa_wallet", lang, usd=usd, cdf=cdf)
        if entries:
            body += "\n\n" + text("wa_wallet_history", lang) + "\n" + "\n".join(self._history_line(entry, lang) for entry in entries)
        else:
            body += "\n\n" + text("wa_wallet_no_history", lang)
        return [meta.Text(body), self._menu(lang, name)], {}

    @staticmethod
    def _history_line(entry: dict, lang: str) -> str:
        amount = str(entry.get("amount") or "0")
        sign = "-" if amount.startswith("-") else "+"
        shown, currency = amount_text(amount.lstrip("-+"), entry.get("currency") or "USD")
        kind = entry.get("kind") or ""
        label = text(f"wa_history_{kind}", lang) if kind in HISTORY_KINDS else text("wa_history_other", lang)
        mission = f" ({reference(entry['mission_id'])})" if entry.get("mission_id") else ""
        day = (entry.get("created_at") or "")[:10]
        return f"• {day} {label}{mission} : {sign}{shown} {currency}".replace("•  ", "• ")

    # --- Refus -------------------------------------------------------------------------------

    async def _refused(self, message, refusal: Refused, mission_id, lang, name):
        if refusal.code in NOT_YOURS or mission_id is None:
            return self._unknown(lang, name)
        if refusal.code == "already_reviewed":
            return [meta.Text(text("wa_rate_already", lang)), self._menu(lang, name)], {}
        if refusal.code == "invalid_rating":
            return self._stars(mission_id, lang, name)
        if refusal.code == "already_settled" and (refusal.detail.get("mission") or {}).get("payment_status") == "released":
            intro = text("wa_follow_already_released", lang, reference=reference(mission_id))
        elif refusal.code in ("invalid_state", "mission_disputed", "already_settled", "not_paid", "invalid_reason"):
            intro = text("wa_follow_changed", lang)
        else:
            return self.conversation._refused(refusal, lang, {}).as_pair()
        # La demande a bougé entre-temps : on montre où elle en est.
        return await self.conversation.quotes._mission(message, mission_id, lang, name, intro=[meta.Text(intro)])

    def _unknown(self, lang, name):
        return [meta.Text(text("wa_mission_unknown", lang)), self._menu(lang, name)], {}


HISTORY_KINDS = frozenset(
    {
        "opening_balance", "fund_wallet", "refund", "split", "overpayment", "mismatch_credit", "agreement",
        "release", "auto_release", "dispute_release", "payout_hold", "payout",
    }
)  # fmt: skip
