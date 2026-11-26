"""Créer une mission en conversation, pas à pas (étape 5 WhatsApp).

Mêmes questions, dans le même ordre, que le bot Telegram
(telegram_bot/mission.py), pour que les mêmes réponses donnent la même
mission en base :

1. service (liste, par pages de 10 lignes au plus) ;
2. urgence (Oui / Non) ;
3. commune (liste) ;
4. lieu exact : bouton « Envoyer la position » de WhatsApp (ou 📎 →
   Position), puis repère écrit ;
5. devise (USD / CDF) ;
6. description, en un message écrit (les photos et vocaux ne sont pas
   encore pris en charge sur WhatsApp) ;
7. récapitulatif : Confirmer, Modifier (tout recommencer) ou Annuler.

Chaque question a « Retour » (la question d'avant) ; « Annuler » ou le mot
« menu » arrêtent tout, sans rien envoyer. Rien n'est créé avant
« Confirmer ».

Le backend décide de tout : catalogue et communes (`/api/services`), lieu
dans Kinshasa, prestataires prévenus. La demande en cours (brouillon) reste
dans l'étape de la conversation (Redis, 24 h), jamais ailleurs.

Doublons : le brouillon reçoit une `creation_key` en arrivant au
récapitulatif, la même pour chaque essai de cette demande. Un double appui
sur « Confirmer » (deux messages) ne crée donc qu'une mission, et le même
message rejoué par Meta rend la même réponse (clé d'idempotence = wamid).
"""

from __future__ import annotations

import logging
import uuid

from messages import get_message
from whatsapp_bot import meta
from whatsapp_bot.backend import Refused

logger = logging.getLogger(__name__)

# Étapes (gardées dans Redis avec le brouillon).
PREFIX = "mission:"
SERVICE = PREFIX + "service"
URGENT = PREFIX + "urgent"
COMMUNE = PREFIX + "commune"
LOCATION = PREFIX + "location"
LANDMARK = PREFIX + "landmark"
CURRENCY = PREFIX + "currency"
DESCRIPTION = PREFIX + "description"
RECAP = PREFIX + "recap"
TERMS = PREFIX + "terms"
# « Retour » mène à la question d'avant.
PREVIOUS = {URGENT: SERVICE, COMMUNE: URGENT, LOCATION: COMMUNE, LANDMARK: LOCATION, CURRENCY: LANDMARK, DESCRIPTION: CURRENCY}

# Identifiants des boutons et lignes.
SERVICE_ROW = "svc:"
COMMUNE_ROW = "com:"
PAGE_ROW = "page:"
URGENT_YES = "m:urgent:yes"
URGENT_NO = "m:urgent:no"
CURRENCY_BUTTON = "m:cur:"
BACK = "m:back"
CANCEL = "m:cancel"
CONFIRM = "m:confirm"
EDIT = "m:edit"
TERMS_ACCEPT = "m:terms:accept"
TERMS_DECLINE = "m:terms:decline"

CURRENCIES = ("USD", "CDF")
# Mêmes bornes que le backend (crud.MIN_LANDMARK_LENGTH / MAX_…, et la
# description de MissionCreatePayload), qui reste seul juge.
MIN_LANDMARK_LENGTH = 3
MAX_LANDMARK_LENGTH = 300
MIN_DESCRIPTION_LENGTH = 3
MAX_DESCRIPTION_LENGTH = 4000
# Mot qui arrête la demande en cours, à n'importe quelle étape.
STOP_WORDS = frozenset({"menu", "annuler", "cancel", "kanga"})

# Refus du backend à la confirmation.
DESTINATION_REFUSALS = frozenset({"destination_outside_service_area", "invalid_destination"})
CATALOGUE_REFUSALS = frozenset({"invalid_mission", "service_not_requestable"})
TERMS_REFUSALS = frozenset({"terms_not_accepted", "terms_version_outdated", "terms_version_not_found"})


def text(key: str, lang: str, **values) -> str:
    return get_message(key, lang, **values)


def is_mission_step(state: dict) -> bool:
    return str(state.get("step") or "").startswith(PREFIX)


def _cut(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "…"


class MissionFlow:
    """`conversation` : pour le menu et les écrans de conditions, communs au
    reste du service (conversation.Conversation)."""

    def __init__(self, conversation) -> None:
        self.conversation = conversation
        self.backend = conversation.backend

    # --- Entrée ------------------------------------------------------------------

    async def start(self, message: meta.Incoming, lang: str) -> tuple[list, dict]:
        return await self._ask(SERVICE, message.bsuid, lang, {"draft": {}})

    async def handle(self, message: meta.Incoming, state: dict, lang: str, name: str) -> tuple[list, dict]:
        """Message reçu pendant une demande. Rend (messages, étape)."""
        step = state.get("step")
        choice = message.choice if message.kind == meta.CHOICE else None
        typed = " ".join((message.text or "").split()) if message.kind == meta.TEXT else None

        if choice == CANCEL or (typed is not None and typed.lower() in STOP_WORDS):
            return [meta.Text(text("wa_request_cancelled", lang)), self.conversation._menu(lang, name)], {}
        if choice == BACK and step in PREVIOUS:
            target = RECAP if step == LOCATION and state.get("back_to_recap") else PREVIOUS[step]
            return await self._ask(target, message.bsuid, lang, state)

        handler = {
            SERVICE: self._on_service,
            URGENT: self._on_urgent,
            COMMUNE: self._on_commune,
            LOCATION: self._on_location,
            LANDMARK: self._on_landmark,
            CURRENCY: self._on_currency,
            DESCRIPTION: self._on_description,
            RECAP: self._on_recap,
            TERMS: self._on_terms,
        }.get(step)
        if handler is None:
            return await self.start(message, lang)
        answer = await handler(message, state, lang, name, choice, typed)
        if answer is not None:
            return answer
        # Pas une réponse à la question en cours : on la repose.
        intro = []
        if message.kind == meta.MEDIA:
            intro = [meta.Text(text("wa_description_text_only" if step == DESCRIPTION else "wa_media_refused", lang))]
        messages, state = await self._ask(step, message.bsuid, lang, state)
        return intro + messages, state

    # --- Réponses, étape par étape ----------------------------------------------------

    async def _on_service(self, message, state, lang, name, choice, typed):
        if choice and choice.startswith(PAGE_ROW):
            return await self._ask(SERVICE, message.bsuid, lang, state, page=_page(choice))
        if not (choice and choice.startswith(SERVICE_ROW)):
            return None
        catalogue = await self.backend.services(message.bsuid)
        key = choice[len(SERVICE_ROW) :]
        if key not in _requestable(catalogue):
            return await self._catalogue_changed(message, lang)
        draft = {"service": key, "service_name": _service_name(catalogue, key, lang)}
        return await self._ask(URGENT, message.bsuid, lang, {"draft": draft})

    async def _on_urgent(self, message, state, lang, name, choice, typed):
        if choice not in (URGENT_YES, URGENT_NO):
            return None
        state = _with(state, urgent=choice == URGENT_YES)
        return await self._ask(COMMUNE, message.bsuid, lang, state)

    async def _on_commune(self, message, state, lang, name, choice, typed):
        if choice and choice.startswith(PAGE_ROW):
            return await self._ask(COMMUNE, message.bsuid, lang, state, page=_page(choice))
        if not (choice and choice.startswith(COMMUNE_ROW)):
            return None
        commune = choice[len(COMMUNE_ROW) :]
        catalogue = await self.backend.services(message.bsuid)
        if commune not in (catalogue.get("communes") or []):
            return await self._catalogue_changed(message, lang)
        return await self._ask(LOCATION, message.bsuid, lang, _with(state, commune=commune))

    async def _on_location(self, message, state, lang, name, choice, typed):
        if message.kind != meta.LOCATION:
            if message.kind in (meta.TEXT, meta.MEDIA):
                return [meta.Text(text("wa_location_required", lang)), *self._location_prompt(lang)], state
            return None
        # Seul le point envoyé compte : une position en direct n'est pas
        # suivie (le client n'est jamais localisé en continu).
        state = _with(state, latitude=message.latitude, longitude=message.longitude)
        return await self._ask(LANDMARK, message.bsuid, lang, state)

    async def _on_landmark(self, message, state, lang, name, choice, typed):
        if typed is None:
            return None
        if not MIN_LANDMARK_LENGTH <= len(typed) <= MAX_LANDMARK_LENGTH:
            return [meta.Text(text("wa_landmark_invalid", lang))], state
        state = _with(state, landmark=typed)
        if state.get("back_to_recap"):
            # Lieu corrigé après un refus : le reste de la demande est gardé.
            return await self._ask(RECAP, message.bsuid, lang, {**state, "back_to_recap": False})
        return await self._ask(CURRENCY, message.bsuid, lang, state)

    async def _on_currency(self, message, state, lang, name, choice, typed):
        if not (choice and choice.startswith(CURRENCY_BUTTON)) or choice[len(CURRENCY_BUTTON) :] not in CURRENCIES:
            return None
        return await self._ask(DESCRIPTION, message.bsuid, lang, _with(state, currency=choice[len(CURRENCY_BUTTON) :]))

    async def _on_description(self, message, state, lang, name, choice, typed):
        if message.kind != meta.TEXT:
            return None
        description = (message.text or "").strip()
        if not MIN_DESCRIPTION_LENGTH <= len(description) <= MAX_DESCRIPTION_LENGTH:
            return [meta.Text(text("wa_description_invalid", lang))], state
        return await self._ask(RECAP, message.bsuid, lang, _with(state, description=description))

    async def _on_recap(self, message, state, lang, name, choice, typed):
        if choice == EDIT:
            return await self.start(message, lang)
        if choice != CONFIRM:
            return None
        return await self._confirm(message, state, lang, name)

    async def _on_terms(self, message, state, lang, name, choice, typed):
        if choice == TERMS_DECLINE:
            return [meta.Text(text("wa_terms_update_declined", lang)), self.conversation._menu(lang, name)], {}
        if choice != TERMS_ACCEPT:
            return None
        try:
            await self.backend.accept_terms(message.bsuid, message.message_id, role="client", documents=state.get("documents") or [])
        except Refused as refusal:
            if refusal.code in TERMS_REFUSALS:
                return await self._show_terms(message, state, lang, changed=True)
            return self.conversation._refused(refusal, lang, state).as_pair()
        # Accepté : la personne relit et confirme sa demande (nouveau message,
        # donc nouvelle clé d'idempotence pour la création).
        return await self._ask(RECAP, message.bsuid, lang, {key: value for key, value in state.items() if key != "documents"})

    # --- Confirmation -----------------------------------------------------------------

    async def _confirm(self, message, state, lang, name):
        draft = state.get("draft") or {}
        try:
            request = {
                "creation_key": draft["creation_key"],
                "service": draft["service"],
                "commune": draft["commune"],
                "currency": draft["currency"],
                "description": draft["description"],
                "urgent": bool(draft["urgent"]),
                "destination": {"latitude": draft["latitude"], "longitude": draft["longitude"], "landmark": draft["landmark"]},
            }
        except KeyError:
            # Brouillon incomplet (ancienne version du service) : on recommence.
            return await self.start(message, lang)
        try:
            answer = await self.backend.create_mission(message.bsuid, message.message_id, request)
        except Refused as refusal:
            if refusal.code in DESTINATION_REFUSALS:
                # Rien n'est créé : le client renvoie le lieu, le reste est gardé.
                messages, state = await self._ask(LOCATION, message.bsuid, lang, {**state, "back_to_recap": True})
                return [meta.Text(text("wa_destination_refused", lang)), *messages], state
            if refusal.code in CATALOGUE_REFUSALS:
                return await self._catalogue_changed(message, lang)
            if refusal.code in TERMS_REFUSALS:
                return await self._show_terms(message, state, lang)
            return self.conversation._refused(refusal, lang, state).as_pair()
        mission = answer.get("mission") or {}
        count = int(answer.get("alerted_provider_count") or 0)
        matching = text("wa_matching_notified", lang, count=count) if count else text("wa_matching_none", lang)
        saved = text("wa_mission_saved", lang, reference=f"NXH-{int(mission['mission_id']):04d}", matching=matching)
        return [meta.Text(saved), self.conversation._menu(lang, name)], {}

    async def _show_terms(self, message, state, lang, changed: bool = False):
        status = await self.backend.terms(message.bsuid)
        documents = [
            {"document_key": item["document_key"], "version": item["version"]}
            for item in (status.get("by_role", {}).get("client") or [])
        ]
        if not documents:
            return [meta.Text(text("terms_unavailable", lang))], {}
        messages = [meta.Text(text("wa_terms_changed", lang))] if changed else []
        messages += await self.conversation._terms_texts(documents, lang)
        listed = "\n".join(self.conversation._document_line(item, lang) for item in documents)
        messages.append(
            meta.Buttons(
                body=text("wa_terms_update", lang, documents=listed),
                buttons=((TERMS_ACCEPT, text("wa_btn_accept", lang)), (TERMS_DECLINE, text("wa_btn_decline", lang))),
            )
        )
        return messages, {**state, "step": TERMS, "documents": documents}

    async def _catalogue_changed(self, message, lang):
        messages, state = await self.start(message, lang)
        return [meta.Text(text("wa_catalogue_changed", lang)), *messages], state

    # --- Questions --------------------------------------------------------------------

    async def _ask(self, step: str, bsuid: str, lang: str, state: dict, page: int = 0) -> tuple[list, dict]:
        """Pose la question de `step` et rend l'étape à garder."""
        state = {**state, "step": step}
        draft = state.get("draft") or {}
        if step == SERVICE:
            catalogue = await self.backend.services(bsuid)
            rows = [
                (f"{SERVICE_ROW}{item['key']}", _cut(_label(item, lang), meta.MAX_ROW_TITLE), "")
                for item in catalogue.get("services") or []
                if item["key"] in _requestable(catalogue)
            ]
            if not rows:
                return [meta.Text(text("wa_no_services", lang))], {}
            extra = ((CANCEL, text("wa_row_cancel", lang), ""),)
            return [_list(text("wa_choose_service", lang), text("wa_list_services", lang), rows, extra, page, lang)], state
        if step == URGENT:
            body = text("wa_is_urgent", lang, service=draft.get("service_name") or "")
            buttons = ((URGENT_YES, text("wa_btn_yes", lang)), (URGENT_NO, text("wa_btn_no", lang)), (BACK, text("wa_btn_back", lang)))
            return [meta.Buttons(body=body, buttons=buttons)], state
        if step == COMMUNE:
            catalogue = await self.backend.services(bsuid)
            rows = [(f"{COMMUNE_ROW}{name}", _cut(name, meta.MAX_ROW_TITLE), "") for name in catalogue.get("communes") or []]
            extra = ((BACK, text("wa_row_back", lang), ""),)
            return [_list(text("wa_choose_commune", lang), text("wa_list_communes", lang), rows, extra, page, lang)], state
        if step == LOCATION:
            return self._location_prompt(lang), state
        if step == LANDMARK:
            return [_with_controls(text("wa_ask_landmark", lang), lang)], state
        if step == CURRENCY:
            buttons = tuple((f"{CURRENCY_BUTTON}{code}", code) for code in CURRENCIES) + ((BACK, text("wa_btn_back", lang)),)
            return [meta.Buttons(body=text("wa_choose_currency", lang), buttons=buttons)], state
        if step == DESCRIPTION:
            return [_with_controls(text("wa_describe", lang), lang)], state
        if step == RECAP:
            if not draft.get("creation_key"):
                # La même clé pour chaque essai de cette demande.
                state = _with(state, creation_key=uuid.uuid4().hex)
                draft = state["draft"]
            buttons = ((CONFIRM, text("wa_btn_confirm", lang)), (EDIT, text("wa_btn_edit", lang)), (CANCEL, text("wa_btn_cancel", lang)))
            return [meta.Buttons(body=_summary(draft, lang), buttons=buttons)], state
        raise ValueError(f"Étape inconnue : {step}")

    def _location_prompt(self, lang: str) -> list:
        return [meta.LocationRequest(text("wa_ask_location", lang)), _with_controls(text("wa_step_controls", lang), lang)]


# --- Aides ------------------------------------------------------------------------------


def _with(state: dict, **values) -> dict:
    return {**state, "draft": {**(state.get("draft") or {}), **values}}


def _page(choice: str) -> int:
    value = choice[len(PAGE_ROW) :]
    return int(value) if value.isdigit() else 0


def _requestable(catalogue: dict) -> set[str]:
    excluded = set(catalogue.get("client_excluded_services") or [])
    return {item["key"] for item in catalogue.get("services") or []} - excluded


def _label(item: dict, lang: str) -> str:
    names = item.get("names") or {}
    name = names.get(lang) or names.get("fr") or item["key"]
    return f"{item['icon']} {name}" if item.get("icon") else name


def _service_name(catalogue: dict, key: str, lang: str) -> str:
    item = next(item for item in catalogue.get("services") or [] if item["key"] == key)
    names = item.get("names") or {}
    return names.get(lang) or names.get("fr") or key


def _list(body: str, button: str, rows: list, extra: tuple, page: int, lang: str) -> meta.Menu:
    """Liste de 10 lignes au plus : les choix de la page, une ligne « Plus de
    choix » s'il en reste (la dernière page revient à la première), puis
    `extra` (Retour, Annuler)."""
    capacity = meta.MAX_LIST_ROWS - len(extra)
    if len(rows) <= capacity:
        shown = list(rows)
    else:
        per_page = capacity - 1
        pages = -(-len(rows) // per_page)
        page = page % pages
        shown = rows[page * per_page : (page + 1) * per_page]
        shown.append((f"{PAGE_ROW}{(page + 1) % pages}", text("wa_row_more", lang), ""))
    return meta.Menu(body=body, button=button, rows=tuple(shown) + tuple(extra))


def _with_controls(body: str, lang: str) -> meta.Buttons:
    return meta.Buttons(body=body, buttons=((BACK, text("wa_btn_back", lang)), (CANCEL, text("wa_btn_cancel", lang))))


def _summary(draft: dict, lang: str) -> str:
    """Récapitulatif dans la limite d'un message à boutons : la description
    est raccourcie à l'écran si besoin (elle part entière au backend)."""
    yes_no = text("wa_btn_yes" if draft.get("urgent") else "wa_btn_no", lang)

    def render(description: str) -> str:
        return text(
            "wa_mission_summary",
            lang,
            service=draft.get("service_name") or "",
            urgent=yes_no,
            commune=draft.get("commune") or "",
            landmark=draft.get("landmark") or "",
            currency=draft.get("currency") or "",
            description=description,
        )

    description = draft.get("description") or ""
    room = meta.MAX_INTERACTIVE_BODY - len(render(""))
    return render(description if len(description) <= room else _cut(description, max(room, 1)))
