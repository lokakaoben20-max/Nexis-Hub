"""Claviers et libellés utilisés par le flow inscription/profil (Phase 3, pilote).

Déplacés depuis `main.py` par nécessité technique, pas par choix de design : un
`from main import ...` dans `telegram_bot/registration.py` casserait le bot lancé via
`python main.py` (le module s'exécute alors sous le nom `__main__`, jamais enregistré
comme `main` dans `sys.modules` — l'import réexécuterait tout `main.py` une seconde
fois, recréant un second `Bot`/`Dispatcher`). `main.py` importe donc SERVICES, COMMUNES,
MINI_APP_URL, button_label et les claviers ci-dessous depuis ce module au lieu de les
définir localement — rien ne change pour les handlers hors scope qui les utilisent.
"""

import os

from aiogram.types import (
    InputRichBlockParagraph,
    InputRichBlockTable,
    InputRichMessage,
    KeyboardButton,
    ReplyKeyboardMarkup,
    RichBlockTableCell,
    WebAppInfo,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

from db import get_active_services
from messages import get_message

load_dotenv()
MINI_APP_URL = os.getenv("MINI_APP_URL")

FALLBACK_SERVICES = {
    "service_plomberie": "🔧 Plomberie",
    "service_electricite": "⚡ Electricité",
    "service_climatisation": "❄️ Climatisation",
    "service_informatique": "💻 Informatique",
    "service_graphisme": "🎨 Graphisme",
    "service_coiffure": "✂️ Coiffure",
    "service_nettoyage": "🧹 Nettoyage",
    "service_jardinage": "🌿 Jardinage",
    "service_autre": "➕ Autre service",
}


def load_services():
    try:
        services = get_active_services("fr", include_icon=True)
        return services or FALLBACK_SERVICES
    except Exception:
        return FALLBACK_SERVICES


SERVICES = load_services()

SERVICE_CALLBACKS = list(SERVICES.keys())

COMMUNES = [
    ("Gombe", "commune_gombe"),
    ("Kinshasa", "commune_kinshasa"),
    ("Limete", "commune_limete"),
    ("Ngaliema", "commune_ngaliema"),
    ("Lemba", "commune_lemba"),
    ("Kalamu", "commune_kalamu"),
    ("Barumbu", "commune_barumbu"),
    ("Lingwala", "commune_lingwala"),
    ("Autre commune", "commune_autre"),
]

CURRENCIES = {
    "currency_usd": "USD",
    "currency_cdf": "CDF",
}
CURRENCY_CALLBACKS = list(CURRENCIES.keys())

BUTTON_LABELS = {
    "fr": {
        "client": "👤 Client",
        "provider": "🔧 Prestataire",
        "request_service": "🔍 Demander un service",
        "my_missions": "📋 Mes missions en cours",
        "history": "📜 Historique",
        "wallet": "👛 Mon Wallet",
        "profile": "👤 Mon profil",
        "help": "❓ Aide",
        "open_mini_app": "🚀 Ouvrir Nexis Hub",
        "dashboard": "📊 Mon tableau de bord",
        "provider_missions": "📋 Mes missions",
        "provider_wallet": "💰 Mon portefeuille",
        "availability": "⚙️ Disponibilité",
        "my_services": "🧰 Mes services",
        "missing_service": "➕ Service manquant",
        "support": "❓ Support",
        "urgent_yes": "🚨 Oui, c'est urgent",
        "urgent_no": "📅 Non, pas urgent",
        "back_services": "⬅️ Retour aux services",
        "back": "⬅️ Retour",
        "back_communes": "⬅️ Retour aux communes",
        "confirm_request": "✅ Confirmer la demande",
        "edit": "✏️ Modifier",
        "cancel": "❌ Annuler",
        "skip_photo": "➡️ Continuer sans photo",
        "finish_explanation": "✅ Terminer l'explication",
        "skip_rating": "➡️ Ne pas noter",
        "skip_comment": "➡️ Envoyer sans commentaire",
        "settings": "✏️ Modifier",
        "change_language": "🌐 Changer de langue",
        "change_name": "✏️ Modifier mon nom",
    },
    "ln": {
        "client": "👤 Client",
        "provider": "🔧 Mosali",
        "request_service": "🔍 Kosenga service",
        "my_missions": "📋 Misala na ngai",
        "history": "📜 Historique",
        "wallet": "👛 Wallet na ngai",
        "profile": "👤 Profil na ngai",
        "help": "❓ Lisungi",
        "open_mini_app": "🚀 Kofungola Nexis Hub",
        "dashboard": "📊 Tableau na ngai",
        "provider_missions": "📋 Misala na ngai",
        "provider_wallet": "💰 Portefeuille na ngai",
        "availability": "⚙️ Disponibilité",
        "my_services": "🧰 Services na ngai",
        "missing_service": "➕ Service ezangi",
        "support": "❓ Lisungi",
        "urgent_yes": "🚨 Ee, ezali urgent",
        "urgent_no": "📅 Te, urgent te",
        "back_services": "⬅️ Zonga na services",
        "back": "⬅️ Zonga",
        "back_communes": "⬅️ Zonga na communes",
        "confirm_request": "✅ Kondima demande",
        "edit": "✏️ Kobongisa",
        "cancel": "❌ Kolongola",
        "skip_photo": "➡️ Kokoba sans photo",
        "finish_explanation": "✅ Nasilisi kolimbola",
        "skip_rating": "➡️ Kopesa note te",
        "skip_comment": "➡️ Kotinda sans commentaire",
        "settings": "✏️ Kobongisa",
        "change_language": "🌐 Kobongola monoko",
        "change_name": "✏️ Kobongola kombo",
    },
    "en": {
        "client": "👤 Client",
        "provider": "🔧 Provider",
        "request_service": "🔍 Request a service",
        "my_missions": "📋 My active missions",
        "history": "📜 History",
        "wallet": "👛 My Wallet",
        "profile": "👤 My profile",
        "help": "❓ Help",
        "open_mini_app": "🚀 Open Nexis Hub",
        "dashboard": "📊 Dashboard",
        "provider_missions": "📋 My missions",
        "provider_wallet": "💰 My wallet",
        "availability": "⚙️ Availability",
        "my_services": "🧰 My services",
        "missing_service": "➕ Missing service",
        "support": "❓ Support",
        "urgent_yes": "🚨 Yes, urgent",
        "urgent_no": "📅 No, not urgent",
        "back_services": "⬅️ Back to services",
        "back": "⬅️ Back",
        "back_communes": "⬅️ Back to communes",
        "confirm_request": "✅ Confirm request",
        "edit": "✏️ Edit",
        "cancel": "❌ Cancel",
        "skip_photo": "➡️ Continue without photo",
        "finish_explanation": "✅ Finish explanation",
        "skip_rating": "➡️ Skip rating",
        "skip_comment": "➡️ Send without comment",
        "settings": "✏️ Edit",
        "change_language": "🌐 Change language",
        "change_name": "✏️ Edit my name",
    },
}


def button_label(key: str, lang: str = "fr") -> str:
    return BUTTON_LABELS.get(lang, BUTTON_LABELS["fr"]).get(key, BUTTON_LABELS["fr"][key])


def clavier_contact(lang: str = "fr"):
    text = {
        "fr": "📱 Partager mon numéro WhatsApp",
        "ln": "📱 Kotinda numéro WhatsApp",
        "en": "📱 Share my WhatsApp number",
    }.get(lang, "📱 Partager mon numéro WhatsApp")
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=text, request_contact=True)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def clavier_langue():
    builder = InlineKeyboardBuilder()
    builder.button(text="🇫🇷 Français", callback_data="lang_fr")
    builder.button(text="🇨🇩 Lingala", callback_data="lang_ln")
    builder.button(text="🇬🇧 English", callback_data="lang_en")
    builder.adjust(1)
    return builder.as_markup()


def clavier_profil(lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    builder.button(text=button_label("client", lang), callback_data="profil_client")
    builder.button(text=button_label("provider", lang), callback_data="profil_prestataire")
    builder.adjust(2)
    return builder.as_markup()


def clavier_client(lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    if MINI_APP_URL:
        builder.button(text=button_label("open_mini_app", lang), web_app=WebAppInfo(url=MINI_APP_URL))
    builder.button(text=button_label("request_service", lang), callback_data="client_demande")
    builder.button(text=button_label("my_missions", lang), callback_data="client_missions")
    builder.button(text=button_label("history", lang), callback_data="client_historique")
    builder.button(text=button_label("wallet", lang), callback_data="client_wallet")
    builder.button(text=button_label("profile", lang), callback_data="client_profil")
    builder.button(text=button_label("help", lang), callback_data="client_aide")
    builder.button(text=button_label("settings", lang), callback_data="client_parametres")
    builder.adjust(1)
    return builder.as_markup()


def clavier_parametres_client(lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    builder.button(text=button_label("change_language", lang), callback_data="client_settings_language")
    builder.button(text=button_label("change_name", lang), callback_data="client_settings_name")
    builder.button(text=button_label("back", lang), callback_data="client_menu_from_settings")
    builder.adjust(1)
    return builder.as_markup()


def clavier_langue_parametres(lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    builder.button(text="🇫🇷 Français", callback_data="settings_lang_fr")
    builder.button(text="🇨🇩 Lingala", callback_data="settings_lang_ln")
    builder.button(text="🇬🇧 English", callback_data="settings_lang_en")
    builder.button(text=button_label("back", lang), callback_data="client_parametres")
    builder.adjust(1)
    return builder.as_markup()


def clavier_prestataire(lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    if MINI_APP_URL:
        builder.button(text=button_label("open_mini_app", lang), web_app=WebAppInfo(url=MINI_APP_URL))
    builder.button(text=button_label("dashboard", lang), callback_data="prest_dashboard")
    builder.button(text=button_label("provider_missions", lang), callback_data="prest_missions")
    builder.button(text=button_label("provider_wallet", lang), callback_data="prest_wallet")
    builder.button(text=button_label("profile", lang), callback_data="prest_profil")
    builder.button(text=button_label("my_services", lang), callback_data="prest_services")
    builder.button(text=button_label("missing_service", lang), callback_data="prest_missing_service")
    builder.button(text=button_label("availability", lang), callback_data="prest_dispo")
    builder.button(text=button_label("support", lang), callback_data="prest_support")
    builder.adjust(1)
    return builder.as_markup()


def clavier_disponibilite(status: str, lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    if status == "available":
        builder.button(text=get_message("button_provider_unavailable", lang), callback_data="provider_status_offline")
    else:
        builder.button(text=get_message("button_provider_available", lang), callback_data="provider_status_available")
    builder.button(text=button_label("back", lang), callback_data="profil_prestataire")
    builder.adjust(1)
    return builder.as_markup()


def clavier_services_prestataire(selected_services=None):
    selected_services = selected_services or []
    builder = InlineKeyboardBuilder()
    for key, label in SERVICES.items():
        prefix = "✅" if key in selected_services else "▫️"
        builder.button(text=f"{prefix} {label}", callback_data=f"provider_service_{key}")
    builder.button(text="➡️ Continuer", callback_data="provider_services_done")
    builder.adjust(1)
    return builder.as_markup()


def clavier_modifier_services(selected_services=None, lang: str = "fr"):
    selected_services = selected_services or []
    builder = InlineKeyboardBuilder()
    for key, label in SERVICES.items():
        prefix = "✅" if key in selected_services else "▫️"
        builder.button(text=f"{prefix} {label}", callback_data=f"edit_service_{key}")
    builder.button(text=get_message("button_save_services", lang), callback_data="edit_services_done")
    builder.button(text=get_message("button_propose_service", lang), callback_data="prest_missing_service")
    builder.button(text=button_label("back", lang), callback_data="profil_prestataire")
    builder.adjust(1)
    return builder.as_markup()


def clavier_services_actions(lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    builder.button(text=get_message("button_edit_services", lang), callback_data="prest_edit_services")
    builder.button(text=get_message("button_propose_service", lang), callback_data="prest_missing_service")
    builder.button(text=button_label("back", lang), callback_data="profil_prestataire")
    builder.adjust(1)
    return builder.as_markup()


def clavier_communes_prestataire(selected_communes=None):
    selected_communes = selected_communes or []
    builder = InlineKeyboardBuilder()
    for label, callback_data in COMMUNES:
        prefix = "✅" if label in selected_communes else "▫️"
        builder.button(text=f"{prefix} {label}", callback_data=f"provider_{callback_data}")
    builder.button(text="✅ Terminer l'inscription", callback_data="provider_communes_done")
    builder.adjust(1)
    return builder.as_markup()


# ── Flow mission / devis (Phase 3, second flow extrait) ────────────────────


def clavier_services(lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    for key, label in SERVICES.items():
        builder.button(text=label, callback_data=key)
    builder.button(text=button_label("back", lang), callback_data="profil_client")
    builder.adjust(2, 2, 2, 2, 1, 1)
    return builder.as_markup()


def clavier_urgence(lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    builder.button(text=button_label("urgent_yes", lang), callback_data="urgent_oui")
    builder.button(text=button_label("urgent_no", lang), callback_data="urgent_non")
    builder.button(text=button_label("back_services", lang), callback_data="client_demande")
    builder.adjust(1)
    return builder.as_markup()


def clavier_communes(lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    for label, callback_data in COMMUNES:
        builder.button(text=label, callback_data=callback_data)
    builder.button(text=button_label("back", lang), callback_data="client_demande")
    builder.adjust(2, 2, 2, 2, 1, 1)
    return builder.as_markup()


def clavier_devises(lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    builder.button(text="💵 USD", callback_data="currency_usd")
    builder.button(text="🇨🇩 CDF", callback_data="currency_cdf")
    builder.button(text=button_label("back_communes", lang), callback_data="back_communes")
    builder.adjust(2, 1)
    return builder.as_markup()


def clavier_devises_devis():
    builder = InlineKeyboardBuilder()
    builder.button(text="💵 USD", callback_data="quote_currency_usd")
    builder.button(text="🇨🇩 CDF", callback_data="quote_currency_cdf")
    builder.adjust(2)
    return builder.as_markup()


def clavier_recapitulatif(lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    builder.button(text=button_label("confirm_request", lang), callback_data="mission_confirmer")
    builder.button(text=button_label("edit", lang), callback_data="client_demande")
    builder.button(text=button_label("cancel", lang), callback_data="mission_annuler")
    builder.adjust(1)
    return builder.as_markup()


def clavier_photo_optionnelle(lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    builder.button(text=button_label("skip_photo", lang), callback_data="mission_skip_photo")
    builder.adjust(1)
    return builder.as_markup()


def clavier_fin_explication(lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    builder.button(text=button_label("finish_explanation", lang), callback_data="mission_media_done")
    builder.button(text=button_label("cancel", lang), callback_data="mission_annuler")
    builder.adjust(1)
    return builder.as_markup()


def clavier_alerte_mission(mission_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Accepter", callback_data=f"provider_accept_{mission_id}")
    builder.button(text="❌ Passer", callback_data=f"provider_skip_{mission_id}")
    builder.adjust(2)
    return builder.as_markup()


def clavier_devis_client(quote_id: int, backend_quote_id: int | None = None):
    backend_suffix = backend_quote_id if backend_quote_id is not None else "-"
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Accepter ce devis", callback_data=f"client_accept_quote_{quote_id}:{backend_suffix}")
    builder.button(text="❌ Refuser", callback_data=f"client_reject_quote_{quote_id}:{backend_suffix}")
    builder.adjust(1)
    return builder.as_markup()


def _parse_quote_callback_ids(raw: str) -> tuple[int, int | None]:
    """Sépare l'id local (db.py) de l'id backend encodés dans un callback_data.

    Les deux séquences d'autoincrement divergent (SQLite vs Postgres) — voir
    V5_MIGRATION_PLAN.md, flow devis. `-` signale un sync backend échoué.
    """
    local_part, _, backend_part = raw.partition(":")
    backend_id = int(backend_part) if backend_part and backend_part != "-" else None
    return int(local_part), backend_id


# ── Vérification prestataire (V5_MIGRATION_PLAN.md) ─────────────────────────


def clavier_portfolio_prestataire(lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    builder.button(text=get_message("provider_portfolio_done_button", lang), callback_data="provider_portfolio_done")
    builder.adjust(1)
    return builder.as_markup()


# ── Flow paiement / lifecycle / notation (Phase 3, flow 3) ─────────────────


def clavier_paiement(quote_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="📱 Payer via Mobile Money", callback_data=f"pay_mobile_{quote_id}")
    builder.button(text="👛 Payer avec Wallet", callback_data=f"pay_wallet_{quote_id}")
    builder.button(text="⬅️ Plus tard", callback_data="profil_client")
    builder.adjust(1)
    return builder.as_markup()


def clavier_mission_prestataire(mission_id: int, action: str, lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    if action == "start":
        builder.button(text=get_message("button_start_mission", lang), callback_data=f"mission_start_{mission_id}")
    elif action == "finish":
        builder.button(text=get_message("button_finish_mission", lang), callback_data=f"mission_finish_{mission_id}")
    builder.button(text=get_message("button_provider_menu", lang), callback_data="profil_prestataire")
    builder.adjust(1)
    return builder.as_markup()


def clavier_confirmation_client(mission_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Confirmer et libérer le paiement", callback_data=f"client_confirm_done_{mission_id}")
    builder.button(text="⚠️ Signaler un problème", callback_data=f"client_report_issue_{mission_id}")
    builder.adjust(1)
    return builder.as_markup()


def clavier_notation(mission_id: int, lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    for i in range(1, 6):
        builder.button(text="⭐" * i, callback_data=f"rate_star_{mission_id}_{i}")
    builder.button(text=button_label("skip_rating", lang), callback_data=f"rate_skip_{mission_id}")
    builder.adjust(1)
    return builder.as_markup()


def clavier_notation_commentaire(mission_id: int, lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    builder.button(text=button_label("skip_comment", lang), callback_data=f"rate_comment_skip_{mission_id}")
    builder.adjust(1)
    return builder.as_markup()


def _rich_cell(text: str, header: bool = False) -> RichBlockTableCell:
    return RichBlockTableCell(text=text, is_header=header, align="left", valign="middle")


def build_quote_accept_rich_message(
    lang: str,
    mission_id: int,
    prestataire: str,
    devis: float,
    total: float,
    currency: str,
    wallet_balance: float,
) -> InputRichMessage:
    rows = [
        (get_message("table_row_provider", lang), prestataire),
        (get_message("table_row_quote", lang), f"{devis:.2f} {currency}"),
        (get_message("table_row_total", lang), f"{total:.2f} {currency}"),
        (get_message("table_row_wallet", lang), f"{wallet_balance:.2f} {currency}"),
    ]
    table = InputRichBlockTable(
        cells=[
            [
                _rich_cell(get_message("table_col_detail", lang), header=True),
                _rich_cell(get_message("table_col_amount", lang), header=True),
            ],
            *[[_rich_cell(label), _rich_cell(value)] for label, value in rows],
        ],
        is_bordered=True,
        is_striped=True,
    )
    return InputRichMessage(
        blocks=[
            InputRichBlockParagraph(text=get_message("quote_accept_title", lang, mission_id=mission_id)),
            table,
            InputRichBlockParagraph(text=get_message("quote_accept_choose_payment", lang)),
        ]
    )


def clavier_admin_new_provider(provider_id: int):
    """Boutons Approuver/Refuser sur la notification admin poussée à l'inscription.

    Mêmes callback_data que clavier_admin_provider (admin_verify_provider_{id} /
    admin_reject_provider_{id}, id interne SQLite) : un seul chemin de code géré
    dans main.py, que l'admin approuve depuis ce push ou depuis la liste
    admin_providers.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Approuver", callback_data=f"admin_verify_provider_{provider_id}")
    builder.button(text="❌ Refuser", callback_data=f"admin_reject_provider_{provider_id}")
    builder.adjust(2)
    return builder.as_markup()
