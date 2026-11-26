"""Ce que le service répond à chaque message (étape 4 : inscription, menu,
refus prestataire, refus des photos, vocaux et documents).

Le backend décide de tout : qui est la personne (`/api/me/profile`), ce
qu'elle doit accepter (`/api/me/terms`), l'inscription et la langue. Ici, on
ne garde que l'étape de la conversation (store.py), et on choisit le
message suivant. Une écriture porte toujours le wamid du message qui l'a
demandée : rejouée, elle ne fait rien de plus.

Parcours d'une personne inconnue :

1. bienvenue et langue (3 boutons) ;
2. prénom (texte) ;
3. conditions d'utilisation : liens de lecture, « J'accepte » ou « Refuser ».
   Rien n'est créé avant « J'accepte » ; l'inscription part au backend avec
   les versions montrées, et un numéro WhatsApp déjà prouvé sur un autre
   compte est refusé par le backend (`phone_owned_by_account`).

Un client inscrit voit le menu (liste). « Nouvelle demande » crée une
mission pas à pas (demande.py, étape 5) ; « Mes missions » et « Mon solde »
arrivent aux étapes 6 et 7.

Un bouton d'une ancienne conversation (étape oubliée après 24 h, ou Redis
vidé) n'est jamais rejeté en silence : la langue choisie est reprise, le
reste recommence à l'étape utile.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from messages import get_message
from whatsapp_bot import demande, meta
from whatsapp_bot.backend import Backend, Refused

logger = logging.getLogger(__name__)

LANGUAGES = ("fr", "ln", "en")
MAX_NAME_LENGTH = 100
# Le texte d'une version des conditions, envoyé dans la conversation quand
# aucune page de lecture n'est configurée (PC de développement).
TEXT_CHUNK = 4000

# Étapes gardées dans Redis.
STEP_LANGUAGE = "language"
STEP_NAME = "name"
STEP_TERMS = "terms"
STEP_CHANGE_LANGUAGE = "change_language"

# Identifiants des boutons et lignes de menu.
LANGUAGE_PREFIX = "lang:"
TERMS_ACCEPT = "terms:accept"
TERMS_DECLINE = "terms:decline"
MENU_NEW_REQUEST = "menu:new_request"
MENU_LANGUAGE = "menu:language"
MENU_PROVIDER = "menu:provider"
MENU_HELP = "menu:help"

# Refus du backend après lesquels on remontre les conditions à jour.
TERMS_CHANGED = frozenset({"terms_version_outdated", "terms_version_not_found", "terms_not_accepted"})


@dataclass
class Outcome:
    """Messages à envoyer, puis étape à garder (vide : rien à garder)."""

    messages: list = field(default_factory=list)
    state: dict = field(default_factory=dict)

    def as_pair(self) -> tuple[list, dict]:
        return self.messages, self.state


@dataclass(frozen=True)
class Links:
    telegram_bot: str | None = None
    mini_app: str | None = None
    # Domaine des pages de lecture des conditions (/conditions/...).
    public_site: str | None = None


def text(key: str, lang: str, **values) -> str:
    return get_message(key, lang, **values)


class Conversation:
    def __init__(self, backend: Backend, links: Links) -> None:
        self.backend = backend
        self.links = links
        self.missions = demande.MissionFlow(self)

    async def handle(self, message: meta.Incoming, state: dict) -> Outcome:
        """Peut lever `BackendUnavailable` : l'appelant prévient la personne,
        sans rien garder à rejouer."""
        if message.kind == meta.IGNORED:
            return Outcome(state=state)
        profile = await self.backend.profile(message.bsuid)
        if profile.get("client"):
            return await self._client(message, state, profile)
        return await self._signup(message, state, profile)

    # --- Inscription -------------------------------------------------------------

    async def _signup(self, message: meta.Incoming, state: dict, profile: dict) -> Outcome:
        step = state.get("step")
        lang = _language(state.get("language") or profile.get("language"))
        choice = message.choice if message.kind == meta.CHOICE else None

        if choice and choice.startswith(LANGUAGE_PREFIX) and _language_of(choice):
            # Aussi depuis un ancien bouton : la langue choisie est reprise.
            lang = _language_of(choice)
            return Outcome([meta.Text(text("wa_ask_name", lang))], {"step": STEP_NAME, "language": lang})

        if step == STEP_NAME and message.kind == meta.TEXT:
            name = " ".join((message.text or "").split())
            if not name or len(name) > MAX_NAME_LENGTH:
                return Outcome([meta.Text(text("wa_name_invalid", lang))], state)
            return await self._show_signup_terms(message.bsuid, lang, name)

        if step == STEP_TERMS and choice == TERMS_ACCEPT:
            return await self._register(message, state, lang)
        if step == STEP_TERMS and choice == TERMS_DECLINE:
            return Outcome([meta.Text(text("wa_terms_declined", lang))], {})

        # Photo, vocal, document : refus, puis la question en cours.
        refusal = [meta.Text(text("wa_media_refused", lang))] if message.kind == meta.MEDIA else []
        if step == STEP_NAME:
            return Outcome(refusal + [meta.Text(text("wa_ask_name", lang))], state)
        if step == STEP_TERMS and state.get("documents"):
            return Outcome(refusal + self._terms_screen("wa_terms_signup", state["documents"], lang), state)
        return Outcome(refusal + [_welcome()], {"step": STEP_LANGUAGE})

    async def _show_signup_terms(self, bsuid: str, lang: str, name: str) -> Outcome:
        try:
            status = await self.backend.terms(bsuid)
        except Refused as refusal:
            return self._refused(refusal, lang, {"step": STEP_NAME, "language": lang})
        documents = _shown(status.get("by_role", {}).get("client") or [])
        if not documents:
            return Outcome([meta.Text(text("terms_unavailable", lang))], {})
        messages = await self._terms_texts(documents, lang)
        messages += self._terms_screen("wa_terms_signup", documents, lang)
        return Outcome(messages, {"step": STEP_TERMS, "language": lang, "name": name, "documents": documents})

    async def _register(self, message: meta.Incoming, state: dict, lang: str) -> Outcome:
        name = state.get("name")
        documents = state.get("documents") or []
        if not name or not documents:
            return Outcome([_welcome()], {"step": STEP_LANGUAGE})
        try:
            await self.backend.register(
                message.bsuid,
                message.message_id,
                name=name,
                language=lang,
                phone=message.phone,
                documents=documents,
            )
        except Refused as refusal:
            if refusal.code == "phone_owned_by_account":
                return Outcome([meta.Text(text("wa_phone_owned", lang))], {})
            if refusal.code == "invalid_name":
                return Outcome([meta.Text(text("wa_name_invalid", lang))], {"step": STEP_NAME, "language": lang})
            if refusal.code in TERMS_CHANGED:
                updated = await self._show_signup_terms(message.bsuid, lang, name)
                return Outcome([meta.Text(text("wa_terms_changed", lang))] + updated.messages, updated.state)
            return self._refused(refusal, lang, state)
        return Outcome(
            [meta.Text(text("wa_registered", lang, name=name)), self._menu(lang, name)],
            {},
        )

    # --- Client inscrit --------------------------------------------------------------

    async def _client(self, message: meta.Incoming, state: dict, profile: dict) -> Outcome:
        lang = _language(profile.get("language"))
        name = (profile.get("client") or {}).get("first_name") or ""
        choice = message.choice if message.kind == meta.CHOICE else None

        if choice and choice.startswith(LANGUAGE_PREFIX) and _language_of(choice):
            new_lang = _language_of(choice)
            try:
                await self.backend.set_language(message.bsuid, message.message_id, new_lang)
            except Refused as refusal:
                return self._refused(refusal, lang, {})
            return Outcome([meta.Text(text("wa_language_updated", new_lang)), self._menu(new_lang, name)], {})
        if choice == MENU_NEW_REQUEST:
            return Outcome(*await self.missions.start(message, lang))
        if choice == MENU_LANGUAGE:
            return Outcome([_language_buttons(text("wa_choose_language", lang))], {"step": STEP_CHANGE_LANGUAGE})
        if choice == MENU_PROVIDER:
            return Outcome([meta.Text(self._provider_refusal(lang))], {})
        if choice == MENU_HELP:
            return Outcome([meta.Text(text("wa_help", lang))], {})
        if demande.is_mission_step(state):
            # Une entrée d'un ancien menu (ci-dessus) quitte la demande en
            # cours ; tout le reste y répond.
            return Outcome(*await self.missions.handle(message, state, lang, name))
        if message.kind == meta.MEDIA:
            return Outcome([meta.Text(text("wa_media_refused", lang)), self._menu(lang, name)], {})
        if message.kind == meta.LOCATION:
            return Outcome([meta.Text(text("wa_not_expected", lang)), self._menu(lang, name)], {})
        return Outcome([self._menu(lang, name)], {})

    # --- Écrans ----------------------------------------------------------------------

    def _menu(self, lang: str, name: str) -> meta.Menu:
        rows = (
            (MENU_NEW_REQUEST, text("wa_menu_new_request", lang), text("wa_menu_new_request_hint", lang)),
            (MENU_LANGUAGE, text("wa_menu_language", lang), text("wa_menu_language_hint", lang)),
            (MENU_PROVIDER, text("wa_menu_provider", lang), text("wa_menu_provider_hint", lang)),
            (MENU_HELP, text("wa_menu_help", lang), text("wa_menu_help_hint", lang)),
        )
        body = text("wa_menu", lang, name=name) if name else text("wa_menu_anonymous", lang)
        return meta.Menu(body=body, button=text("wa_menu_button", lang), rows=rows)

    def _provider_refusal(self, lang: str) -> str:
        lines = []
        if self.links.telegram_bot:
            lines.append(text("wa_provider_link_bot", lang, url=self.links.telegram_bot))
        if self.links.mini_app:
            lines.append(text("wa_provider_link_app", lang, url=self.links.mini_app))
        links = "\n".join(lines) or text("wa_provider_no_link", lang)
        return text("wa_provider_refused", lang, links=links)

    def _terms_screen(self, key: str, documents: list[dict], lang: str) -> list:
        listed = "\n".join(self._document_line(item, lang) for item in documents)
        return [
            meta.Buttons(
                body=text(key, lang, documents=listed),
                buttons=((TERMS_ACCEPT, text("wa_btn_accept", lang)), (TERMS_DECLINE, text("wa_btn_decline", lang))),
            )
        ]

    def _document_line(self, item: dict, lang: str) -> str:
        label = text(f"terms_doc_{item['document_key']}", lang)
        url = self._page_url(item, lang)
        return text("wa_terms_doc_link", lang, document=label, url=url) if url else f"• {label}"

    def _page_url(self, item: dict, lang: str) -> str | None:
        if not self.links.public_site:
            return None
        return f"{self.links.public_site}/conditions/{item['document_key']}/{item['version']}?lang={lang}"

    async def _terms_texts(self, documents: list[dict], lang: str) -> list:
        """Sans page de lecture (PC) : le texte exact de chaque version, dans
        la conversation, avant la question."""
        if self.links.public_site:
            return []
        messages = []
        for item in documents:
            body = await self.backend.terms_text(item["document_key"], item["version"])
            label = text(f"terms_doc_{item['document_key']}", lang)
            messages.append(meta.Text(text("wa_terms_text_header", lang, document=label, version=item["version"])))
            content = body.get("text") or ""
            messages += [meta.Text(content[start : start + TEXT_CHUNK]) for start in range(0, len(content), TEXT_CHUNK)]
        return messages

    def _refused(self, refusal: Refused, lang: str, state: dict) -> Outcome:
        if refusal.code == "terms_unavailable":
            return Outcome([meta.Text(text("terms_unavailable", lang))], {})
        logger.warning("Refus du backend non prévu ici : %s", refusal.code)
        return Outcome([meta.Text(text("wa_error", lang))], state)


def _language(value) -> str:
    return value if value in LANGUAGES else "fr"


def _language_of(choice: str) -> str | None:
    value = choice[len(LANGUAGE_PREFIX) :]
    return value if value in LANGUAGES else None


def _shown(documents: list[dict]) -> list[dict]:
    """Ce qui part au backend : les versions montrées, rien d'autre."""
    return [{"document_key": item["document_key"], "version": item["version"]} for item in documents]


def _language_buttons(body: str) -> meta.Buttons:
    return meta.Buttons(
        body=body,
        buttons=tuple((f"{LANGUAGE_PREFIX}{lang}", text("wa_language_name", lang)) for lang in LANGUAGES),
    )


def _welcome() -> meta.Buttons:
    # Langue encore inconnue : le même texte trilingue dans les trois fichiers.
    return _language_buttons(text("wa_welcome", "fr"))
