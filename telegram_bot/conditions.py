"""La case des conditions d'utilisation dans le bot Telegram.

Le backend décide (backend/app/conditions.py) ; le bot montre la case :

- **À l'inscription** (client, prestataire, bascule client -> prestataire) :
  dernier écran de l'inscription, case « J'ai lu et j'accepte » et
  « Valider ». Telegram n'a pas de vraie case à cocher : un bouton passe de
  ☐ à ☑️. L'inscription part au backend avec la case cochée, ou ne part pas
  (registration.py).
- **Nouvelle version en vigueur** (ou compte d'avant la règle) : le filtre
  `ConditionsGate` passe devant chaque nouvelle action et montre la case
  tant qu'elle n'est pas cochée. Ce que le backend laisse toujours faire
  (lire, finir une mission en cours, litige, retirer son argent, langue,
  admin) n'est pas filtré.

Backend injoignable : on bloque (on ne sait pas si la case manque), comme
pour l'argent. Rien de publié : on bloque aussi, avec un message clair.
"""

import html
import logging
import time
from urllib.parse import urlsplit

from aiogram import BaseMiddleware, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from messages import get_message
from telegram_bot import backend_client
from telegram_bot.backend_client import BackendUnavailable, MoneyRefused

logger = logging.getLogger(__name__)

router = Router()

SURFACE = "telegram_bot"
# Préfixes des boutons de l'écran : `terms_signup_*` pendant une inscription
# (registration.py), `terms_again_*` pour recocher (ce module).
SIGNUP = "terms_signup"
AGAIN = "terms_again"
READ = "terms_read"
# Un texte Telegram fait au plus 4096 caractères.
CHUNK = 3500

# --- Ce que le filtre laisse passer ----------------------------------------------
# Tout le reste est une nouvelle action : la case doit être cochée avant.
EXEMPT_CALLBACK_PREFIXES = (
    "terms_",
    # Langue, choix du profil et inscription (l'inscription porte la case).
    "lang_",
    "profil_client",
    "profil_prestataire",
    "settings_lang_",
    "client_settings_",
    "client_parametres",
    "client_menu_from_settings",
    # Lire : profil, missions, historique, portefeuille, aide.
    "client_profil",
    "client_missions",
    "client_historique",
    "client_wallet",
    "client_aide",
    "prest_profil",
    "prest_missions",
    "prest_wallet",
    "prest_dispo",
    # Se mettre hors ligne, refuser une alerte ou un devis : jamais bloqué.
    "provider_status_offline",
    "provider_skip_",
    "quote_reject_",
    # Mission en cours : arrivée, fin, confirmation, problème, litige, note.
    "presence_",
    "mission_finish_",
    "client_confirm_done_",
    "client_report_issue_",
    "dispute_contest_",
    "doffer_",
    "rate_",
    "check_mm_",
    # Retirer son propre argent.
    "wallet_withdraw",
    "wd_",
    # Admin : l'équipe exploite la plateforme.
    "admin_",
)
# Étapes en cours qui ne sont pas filtrées (groupe d'états aiogram).
EXEMPT_STATE_GROUPS = (
    "ClientRegistration",
    "ProviderRegistration",
    "AppLogin",
    "WithdrawFlow",
    "RatingFlow",
    "DisputeFlow",
    "AdminDisputeSplit",
    "AdminAdditionReason",
    "ClientSettings",
)
EXEMPT_COMMANDS = ("/start", "/app", "/admin", "/couper_app", "/interrupteurs", "/couper", "/rouvrir")

# Résultat « rien ne manque » gardé quelques minutes par personne. Une
# nouvelle version est donc montrée au plus tard ce délai après son entrée
# en vigueur ; le backend, lui, refuse dès la première seconde.
COMPLETE_TTL_SECONDS = 300
_complete_until: dict[int, float] = {}


def forget(telegram_id: int) -> None:
    _complete_until.pop(telegram_id, None)


def _remember_complete(telegram_id: int) -> None:
    _complete_until[telegram_id] = time.monotonic() + COMPLETE_TTL_SECONDS


def _known_complete(telegram_id: int) -> bool:
    return _complete_until.get(telegram_id, 0.0) > time.monotonic()


# Le backend a refusé une action faute de case cochée : on oublie le « rien
# ne manque » gardé, l'action suivante montre la case.
backend_client.on_terms_refused(forget)


# --- L'écran -------------------------------------------------------------------------


def document_label(document_key: str, lang: str) -> str:
    return get_message(f"terms_doc_{document_key}", lang)


def page_url(document_key: str, version: str, lang: str) -> str | None:
    """Page de lecture servie par la Mini App (`/conditions/...`), sur le
    même domaine qu'elle. Sans adresse publique configurée : None, le texte
    est alors envoyé dans la conversation."""
    from telegram_bot.keyboards import MINI_APP_URL

    parts = urlsplit(MINI_APP_URL or "")
    if parts.scheme != "https" or not parts.netloc:
        return None
    return f"https://{parts.netloc}/conditions/{document_key}/{version}?lang={lang}"


def screen_text(kind: str, documents: list[dict], lang: str) -> str:
    """`kind` : terms_signup_client, terms_signup_provider ou terms_again."""
    listed = "\n".join(f"• {html.escape(document_label(item['document_key'], lang))}" for item in documents)
    return get_message(kind, lang, documents=listed)


def keyboard(prefix: str, documents: list[dict], ticked: bool, lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in documents:
        label = get_message("terms_read", lang, document=document_label(item["document_key"], lang))
        url = page_url(item["document_key"], item["version"], lang)
        if url:
            builder.button(text=label, url=url)
        else:
            builder.button(text=label, callback_data=f"{READ}:{item['document_key']}:{item['version']}")
    builder.button(
        text=get_message("terms_checkbox_on" if ticked else "terms_checkbox_off", lang), callback_data=f"{prefix}_tick"
    )
    builder.button(text=get_message("terms_validate", lang), callback_data=f"{prefix}_ok")
    builder.adjust(1)
    return builder.as_markup()


def shown(documents: list[dict]) -> list[dict]:
    """Ce qui part au backend : les versions montrées, rien d'autre."""
    return [{"document_key": item["document_key"], "version": item["version"]} for item in documents]


async def toggle(callback: CallbackQuery, state: FSMContext, prefix: str) -> None:
    data = await state.get_data()
    documents = data.get("terms_documents") or []
    ticked = not data.get("terms_ticked", False)
    await state.update_data(terms_ticked=ticked)
    lang = data.get("language", "fr")
    await callback.message.edit_reply_markup(reply_markup=keyboard(prefix, documents, ticked, lang))
    await callback.answer()


@router.callback_query(F.data.startswith(f"{READ}:"))
async def read_document(callback: CallbackQuery, state: FSMContext):
    """Sans page de lecture : le texte exact de la version, dans la
    conversation, en morceaux."""
    _, document_key, version = callback.data.split(":", 2)
    lang = (await state.get_data()).get("language") or await backend_client.get_language(callback.from_user)
    try:
        body = await backend_client.read_terms(document_key, version)
    except (BackendUnavailable, MoneyRefused):
        await callback.answer(get_message("service_unavailable", lang), show_alert=True)
        return
    await callback.message.answer(
        get_message("terms_text_header", lang, document=html.escape(document_label(document_key, lang)), version=html.escape(version)),
        parse_mode="HTML",
    )
    text = body["text"]
    for start in range(0, len(text), CHUNK):
        await callback.message.answer(text[start : start + CHUNK])
    await callback.answer()


# --- Recocher (nouvelle version, compte d'avant la règle) ---------------------------


async def show_again(target: Message, state: FSMContext, status: dict, lang: str) -> None:
    documents = status["missing"]
    await state.update_data(terms_documents=documents, terms_ticked=False, terms_role=status["role"], language=lang)
    await target.answer(
        screen_text(AGAIN, documents, lang), parse_mode="HTML", reply_markup=keyboard(AGAIN, documents, False, lang)
    )


@router.callback_query(F.data == f"{AGAIN}_tick")
async def tick_again(callback: CallbackQuery, state: FSMContext):
    await toggle(callback, state, AGAIN)


@router.callback_query(F.data == f"{AGAIN}_ok")
async def confirm_again(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language") or await backend_client.get_language(callback.from_user)
    documents = data.get("terms_documents")
    if not documents:
        # Écran d'une ancienne conversation : on redemande au backend.
        await callback.answer()
        await _refresh_again(callback, state, lang)
        return
    if not data.get("terms_ticked"):
        await callback.answer(get_message("terms_must_tick", lang), show_alert=True)
        return
    try:
        status = await backend_client.accept_terms(callback.from_user.id, data["terms_role"], shown(documents), SURFACE)
    except MoneyRefused as error:
        if error.code in ("terms_version_outdated", "terms_version_not_found"):
            await callback.answer(get_message("terms_changed", lang), show_alert=True)
            await _refresh_again(callback, state, lang)
            return
        await callback.answer(backend_client.money_failure_text(0, error, lang, "service_unavailable"), show_alert=True)
        return
    except BackendUnavailable:
        await callback.answer(get_message("service_unavailable", lang), show_alert=True)
        return
    await state.update_data(terms_documents=None, terms_ticked=False, terms_role=None)
    if not status.get("missing"):
        _remember_complete(callback.from_user.id)
        await callback.message.edit_text(get_message("terms_thanks", lang))
        await callback.answer()
        return
    await _refresh_again(callback, state, lang)
    await callback.answer()


async def _refresh_again(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    try:
        status = await backend_client.terms_status(callback.from_user.id)
    except (BackendUnavailable, MoneyRefused) as error:
        await callback.message.answer(backend_client.money_failure_text(0, error, lang, "service_unavailable"))
        return
    if status["missing"]:
        await show_again(callback.message, state, status, lang)
    else:
        _remember_complete(callback.from_user.id)
        await callback.message.answer(get_message("terms_thanks", lang))


# --- Le filtre ---------------------------------------------------------------------


def is_exempt(event, raw_state: str | None) -> bool:
    if raw_state and raw_state.split(":", 1)[0] in EXEMPT_STATE_GROUPS:
        return True
    if isinstance(event, CallbackQuery):
        return bool(event.data) and event.data.startswith(EXEMPT_CALLBACK_PREFIXES)
    if isinstance(event, Message):
        command = (event.text or "").split(maxsplit=1)[0].split("@", 1)[0] if event.text else ""
        return command in EXEMPT_COMMANDS
    return False


class ConditionsGate(BaseMiddleware):
    """Passe devant chaque message et chaque bouton (dp.message,
    dp.callback_query). Une nouvelle action n'est exécutée que si la
    personne a coché la version en vigueur des conditions de ses rôles."""

    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user is None or is_exempt(event, data.get("raw_state")) or _known_complete(user.id):
            return await handler(event, data)
        try:
            status = await backend_client.terms_status(user.id)
        except (BackendUnavailable, MoneyRefused) as error:
            lang = await backend_client.get_language(user)
            text = (
                get_message("terms_unavailable", lang)
                if isinstance(error, MoneyRefused) and error.code == "terms_unavailable"
                else get_message("service_unavailable", lang)
            )
            await _say(event, text)
            return None
        if not status["missing"]:
            _remember_complete(user.id)
            return await handler(event, data)
        lang = await backend_client.get_language(user)
        state: FSMContext | None = data.get("state")
        target = event.message if isinstance(event, CallbackQuery) else event
        if isinstance(event, CallbackQuery):
            await event.answer()
        if state is not None and target is not None:
            await show_again(target, state, status, lang)
        return None


async def _say(event, text: str) -> None:
    if isinstance(event, CallbackQuery):
        await event.answer(text, show_alert=True)
    elif isinstance(event, Message):
        await event.answer(text)
