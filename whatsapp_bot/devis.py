"""« Mes demandes » et les devis (étape 6 WhatsApp).

Le client retrouve ses dernières demandes, leur état et leurs devis, et
choisit : Accepter ou Refuser. Les boutons d'un devis portent les mêmes
identifiants que ceux des notifications du backend
(`evenements.quote_buttons` : `quote_accept_<n>`, `quote_reject_<n>`) :
qu'il vienne de « Mes demandes » ou d'une notification, un appui fait la
même chose.

Le backend décide de tout (un seul devis accepté par mission, seul le client
décide) ; chaque décision porte le wamid du message, un message rejoué ne
fait rien de plus. Aucun montant n'est calculé ici : ceux du backend sont
seulement mis en forme.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from messages import get_message
from whatsapp_bot import meta
from whatsapp_bot.backend import Refused

MISSION_ROW = "mis:"
QUOTE_ACCEPT = "quote_accept_"
QUOTE_REJECT = "quote_reject_"
TERMS_STEP = "quote:terms"
TERMS_ACCEPT = "q:terms:accept"
TERMS_DECLINE = "q:terms:decline"
# Lignes de liste : 10 au plus, une est gardée pour revenir au menu.
MAX_MISSIONS = 9

TERMS_REFUSALS = frozenset({"terms_not_accepted", "terms_version_outdated", "terms_version_not_found"})
UNKNOWN_REFUSALS = frozenset({"quote_not_found", "not_mission_client", "mission_account_missing"})


def text(key: str, lang: str, **values) -> str:
    return get_message(key, lang, **values)


def reference(mission_id: int) -> str:
    return f"NXH-{int(mission_id):04d}"


def amount_text(amount, currency: str) -> tuple[str, str]:
    """Même règle d'affichage que le backend (evenements.amount_text) : USD
    avec 2 décimales, francs congolais sans décimales."""
    try:
        value = Decimal(str(amount))
    except InvalidOperation:
        return str(amount), currency
    if currency == "CDF":
        return f"{value:,.0f}".replace(",", " "), "FC"
    return f"{value:.2f}", currency


def handles(choice: str | None, state: dict) -> bool:
    if state.get("step") == TERMS_STEP:
        return True
    return bool(choice) and choice.startswith((MISSION_ROW, QUOTE_ACCEPT, QUOTE_REJECT))


def _number(choice: str, prefix: str) -> int | None:
    value = choice[len(prefix) :]
    return int(value) if value.isdigit() else None


class QuotesFlow:
    def __init__(self, conversation) -> None:
        self.conversation = conversation
        self.backend = conversation.backend

    async def missions(self, message: meta.Incoming, lang: str, name: str) -> tuple[list, dict]:
        answer = await self.backend.my_missions(message.bsuid, limit=MAX_MISSIONS)
        missions = answer.get("missions") or []
        if not missions:
            return [meta.Text(text("wa_no_missions", lang)), self.conversation._menu(lang, name)], {}
        names = await self._service_names(message.bsuid, lang)
        rows = tuple(
            (
                f"{MISSION_ROW}{mission['mission_id']}",
                _cut(f"{reference(mission['mission_id'])} {names.get(mission['service'], '')}".strip(), meta.MAX_ROW_TITLE),
                _cut(status_label(mission, lang), meta.MAX_ROW_DESCRIPTION),
            )
            for mission in missions[:MAX_MISSIONS]
        )
        menu = meta.Menu(body=text("wa_choose_mission", lang), button=text("wa_list_missions", lang), rows=rows)
        return [menu], {}

    async def handle(self, message: meta.Incoming, state: dict, lang: str, name: str) -> tuple[list, dict]:
        choice = message.choice if message.kind == meta.CHOICE else None
        if state.get("step") == TERMS_STEP:
            return await self._on_terms(message, state, lang, name, choice)
        if choice.startswith(MISSION_ROW):
            mission_id = _number(choice, MISSION_ROW)
            return await self._mission(message, mission_id, lang, name)
        quote_id = _number(choice, QUOTE_ACCEPT if choice.startswith(QUOTE_ACCEPT) else QUOTE_REJECT)
        if quote_id is None:
            return [meta.Text(text("wa_quote_unknown", lang)), self.conversation._menu(lang, name)], {}
        if choice.startswith(QUOTE_ACCEPT):
            return await self._accept(message, quote_id, lang, name)
        return await self._reject(message, quote_id, lang, name)

    # --- Une demande et ses devis --------------------------------------------------

    async def _mission(self, message, mission_id, lang, name, intro=()):
        if mission_id is None:
            return [meta.Text(text("wa_mission_unknown", lang)), self.conversation._menu(lang, name)], {}
        try:
            answer = await self.backend.mission_quotes(message.bsuid, mission_id)
        except Refused as refusal:
            if refusal.code == "mission_not_found":
                return [meta.Text(text("wa_mission_unknown", lang)), self.conversation._menu(lang, name)], {}
            raise
        mission = answer.get("mission") or {}
        quotes = answer.get("quotes") or []
        names = await self._service_names(message.bsuid, lang)
        header = text(
            "wa_mission_header",
            lang,
            reference=reference(mission["mission_id"]),
            service=names.get(mission.get("service"), mission.get("service") or ""),
            commune=mission.get("commune") or "",
            status=status_label(mission, lang),
        )
        messages = list(intro) + [meta.Text(header)]
        accepted = [quote for quote in quotes if quote.get("status") == "accepted"]
        open_quotes = [quote for quote in quotes if quote.get("status") == "pending"]
        for quote in accepted:
            amount, currency = amount_text(quote["amount"], quote["currency"])
            messages.append(meta.Text(text("wa_quote_accepted_line", lang, amount=amount, currency=currency, provider=_provider(quote))))
            if _unpaid(mission):
                messages.append(await self.conversation.payments.pay_card(message.bsuid, {**quote, "mission_id": mission["mission_id"]}, lang))
        if not accepted:
            messages += [self._quote_card(quote, lang) for quote in open_quotes]
            if not open_quotes and mission.get("status") in ("pending", "quoted"):
                messages.append(meta.Text(text("wa_no_quotes_yet", lang)))
        messages.append(self.conversation._menu(lang, name))
        return messages, {}

    def _quote_card(self, quote: dict, lang: str) -> meta.Buttons:
        amount, currency = amount_text(quote["amount"], quote["currency"])
        body = text(
            "wa_quote",
            lang,
            provider=_provider(quote),
            trust=trust_line(quote.get("provider_trust") or {}, lang),
            amount=amount,
            currency=currency,
            delay=quote.get("delay_hours"),
            message=_cut(quote.get("message") or "—", 400),
        )
        buttons = (
            (f"{QUOTE_ACCEPT}{quote['id']}", text("wa_btn_quote_accept", lang)),
            (f"{QUOTE_REJECT}{quote['id']}", text("wa_btn_quote_reject", lang)),
        )
        return meta.Buttons(body=_cut(body, meta.MAX_INTERACTIVE_BODY), buttons=buttons)

    # --- Décisions ---------------------------------------------------------------------

    async def _accept(self, message, quote_id, lang, name):
        try:
            answer = await self.backend.accept_quote(message.bsuid, message.message_id, quote_id)
        except Refused as refusal:
            return await self._refused(message, refusal, quote_id, lang, name)
        quote = answer["quote"]
        amount, currency = amount_text(quote["amount"], quote["currency"])
        accepted = text(
            "wa_quote_accepted",
            lang,
            reference=reference(quote["mission_id"]),
            provider=_provider(quote),
            amount=amount,
            currency=currency,
        )
        if not _unpaid(answer.get("mission") or {}):
            return [meta.Text(accepted), self.conversation._menu(lang, name)], {}
        # Devis accepté : la demande se paie tout de suite, ou plus tard
        # depuis « Mes demandes ».
        return [meta.Text(accepted), await self.conversation.payments.pay_card(message.bsuid, quote, lang)], {}

    async def _reject(self, message, quote_id, lang, name):
        try:
            answer = await self.backend.reject_quote(message.bsuid, message.message_id, quote_id)
        except Refused as refusal:
            return await self._refused(message, refusal, quote_id, lang, name)
        rejected = text("wa_quote_rejected", lang, reference=reference(answer["quote"]["mission_id"]))
        return [meta.Text(rejected), self.conversation._menu(lang, name)], {}

    async def _refused(self, message, refusal: Refused, quote_id, lang, name):
        if refusal.code in UNKNOWN_REFUSALS:
            return [meta.Text(text("wa_quote_unknown", lang)), self.conversation._menu(lang, name)], {}
        if refusal.code == "quote_not_open":
            mission_id = (refusal.detail.get("mission") or {}).get("mission_id")
            if mission_id is None:
                mission_id = ((await self.backend.quote(message.bsuid, quote_id)).get("quote") or {}).get("mission_id")
            return await self._mission(message, mission_id, lang, name, intro=[meta.Text(text("wa_quote_closed", lang))])
        if refusal.code in TERMS_REFUSALS:
            return await self._show_terms(message, quote_id, lang)
        return self.conversation._refused(refusal, lang, {}).as_pair()

    # --- Nouvelles conditions -------------------------------------------------------------

    async def _show_terms(self, message, quote_id, lang):
        status = await self.backend.terms(message.bsuid)
        documents = [
            {"document_key": item["document_key"], "version": item["version"]}
            for item in (status.get("by_role", {}).get("client") or [])
        ]
        if not documents:
            return [meta.Text(text("terms_unavailable", lang))], {}
        messages = await self.conversation._terms_texts(documents, lang)
        listed = "\n".join(self.conversation._document_line(item, lang) for item in documents)
        messages.append(
            meta.Buttons(
                body=text("wa_terms_update_generic", lang, documents=listed),
                buttons=((TERMS_ACCEPT, text("wa_btn_accept", lang)), (TERMS_DECLINE, text("wa_btn_decline", lang))),
            )
        )
        return messages, {"step": TERMS_STEP, "documents": documents, "quote_id": quote_id}

    async def _on_terms(self, message, state, lang, name, choice):
        if choice == TERMS_DECLINE:
            return [meta.Text(text("wa_terms_update_generic_declined", lang)), self.conversation._menu(lang, name)], {}
        if choice != TERMS_ACCEPT:
            # Autre chose qu'une réponse : on repose la question.
            return await self._show_terms(message, state.get("quote_id"), lang)
        try:
            await self.backend.accept_terms(message.bsuid, message.message_id, role="client", documents=state.get("documents") or [])
        except Refused as refusal:
            if refusal.code in TERMS_REFUSALS:
                messages, state = await self._show_terms(message, state.get("quote_id"), lang)
                return [meta.Text(text("wa_terms_changed", lang)), *messages], state
            return self.conversation._refused(refusal, lang, {}).as_pair()
        # Conditions acceptées : le devis est remontré, la personne décide
        # par un nouvel appui (nouveau message, nouvelle clé).
        quote_id = state.get("quote_id")
        try:
            quote = (await self.backend.quote(message.bsuid, int(quote_id))).get("quote") or {}
        except (Refused, TypeError, ValueError):
            return [self.conversation._menu(lang, name)], {}
        return await self._mission(message, quote.get("mission_id"), lang, name)

    async def _service_names(self, bsuid: str, lang: str) -> dict:
        catalogue = await self.backend.services(bsuid)
        return {
            item["key"]: (item.get("names") or {}).get(lang) or (item.get("names") or {}).get("fr") or item["key"]
            for item in catalogue.get("services") or []
        }


def status_label(mission: dict, lang: str) -> str:
    status = mission.get("status")
    if status == "confirmed":
        key = "wa_status_confirmed_paid" if mission.get("payment_status") == "paid_escrow" else "wa_status_confirmed_unpaid"
    elif status in ("pending", "quoted", "in_progress", "awaiting_confirmation", "completed", "cancelled", "disputed"):
        key = f"wa_status_{status}"
    else:
        key = "wa_status_other"
    return text(key, lang)


def _unpaid(mission: dict) -> bool:
    """Devis accepté, argent pas encore bloqué : la demande est à payer."""
    return mission.get("status") == "confirmed" and mission.get("payment_status") in (None, "unpaid")


def trust_line(trust: dict, lang: str) -> str:
    if not trust.get("total_missions"):
        line = text("wa_trust_new", lang)
    else:
        line = text("wa_trust", lang, rating=f"{float(trust.get('rating') or 0):.1f}", missions=int(trust["total_missions"]))
    if trust.get("is_verified"):
        line += text("wa_trust_verified", lang)
    return line


def _provider(quote: dict) -> str:
    return quote.get("provider_name") or "—"


def _cut(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "…"
