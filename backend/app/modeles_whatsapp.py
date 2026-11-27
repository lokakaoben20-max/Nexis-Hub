"""Modèle WhatsApp des notifications hors de la fenêtre de 24 h (étape 8).

Meta ne laisse écrire librement à une personne que dans les 24 h qui suivent
son dernier message. Au-delà, seul un **modèle** soumis et approuvé par Meta
peut partir. Nexis n'en utilise qu'un, de catégorie « utilité » :

    nexis_suivi (fr) : « Bonjour, ici NexisHub. {{1}} Touchez le bouton
    ci-dessous pour voir les détails. »  [Voir les détails]

`{{1}}` est une phrase courte et factuelle, propre à chaque notification
(`PHRASES`), qui nomme la demande et l'état, jamais un montant ni un code. Le
bouton renvoie au bon endroit de la conversation (`button_payload`) : la
demande (`mis:<n>`, comme une ligne de « Mes demandes »), le solde ou la
liste des demandes. Le détail complet (montants, boutons Accepter, Confirmer...)
s'affiche alors, dans la fenêtre rouverte par l'appui.

Langues : Meta n'accepte pas le lingala pour les modèles (liste des langues
de Meta). Un client lingala reçoit le modèle français ; tout le reste de la
conversation reste en lingala. C'est aussi pourquoi les phrases sont ici et
non dans translations/*.json : elles n'existent qu'en français et en anglais,
les deux langues du modèle.

`python -m backend.app.modeles_whatsapp` écrit les modèles au format de
l'API de Meta (création de modèle), prêts à soumettre.
"""

from __future__ import annotations

import json
import re

TEMPLATE_NAME = "nexis_suivi"
CATEGORY = "UTILITY"
# Langue de la personne → langue du modèle chez Meta.
TEMPLATE_LANGUAGE = {"fr": "fr", "ln": "fr", "en": "en"}

BODY = {
    "fr": "Bonjour, ici NexisHub. {{1}} Touchez le bouton ci-dessous pour voir les détails.",
    "en": "Hello, this is NexisHub. {{1}} Tap the button below to see the details.",
}
BUTTON = {"fr": "Voir les détails", "en": "See details"}
EXAMPLE = {
    "fr": "Vous avez reçu un devis pour votre demande NXH-0042.",
    "en": "You have received a quote for your request NXH-0042.",
}

# Phrase {{1}} par texte de notification. `{ref}` : la demande (NXH-0042),
# `{reference}` : un besoin signalé (BES-0007).
PHRASES: dict[str, dict[str, str]] = {
    "new_quote_received_client": {
        "fr": "Vous avez reçu un devis pour votre demande {ref}.",
        "en": "You have received a quote for your request {ref}.",
    },
    "payment_mobile_confirmed_client": {
        "fr": "Votre paiement pour la demande {ref} est confirmé.",
        "en": "Your payment for request {ref} is confirmed.",
    },
    "payment_mobile_failed_client": {
        "fr": "Le paiement de la demande {ref} n'a pas abouti. Rien n'a été débité.",
        "en": "The payment for request {ref} did not go through. Nothing was charged.",
    },
    "payment_overpaid_client": {
        "fr": "Un paiement en trop pour la demande {ref} a été crédité sur votre solde NexisHub.",
        "en": "An extra payment for request {ref} was credited to your NexisHub balance.",
    },
    "payment_mismatch_client": {
        "fr": "Le montant reçu pour la demande {ref} ne correspond pas au devis. Notre équipe vérifie.",
        "en": "The amount received for request {ref} does not match the quote. Our team is checking.",
    },
    "payment_mismatch_credited_client": {
        "fr": "Le montant reçu pour la demande {ref} a été vérifié et crédité sur votre solde NexisHub.",
        "en": "The amount received for request {ref} was checked and credited to your NexisHub balance.",
    },
    "payment_mismatch_paid_client": {
        "fr": "Le montant reçu pour la demande {ref} a été vérifié : la demande est payée.",
        "en": "The amount received for request {ref} was checked: the request is paid.",
    },
    "payout_processing": {
        "fr": "Votre retrait est en cours d'envoi.",
        "en": "Your withdrawal is being sent.",
    },
    "payout_succeeded": {
        "fr": "Votre retrait a été envoyé.",
        "en": "Your withdrawal has been sent.",
    },
    "payout_returned": {
        "fr": "Votre retrait n'a pas été envoyé. Le montant est revenu sur votre solde NexisHub.",
        "en": "Your withdrawal was not sent. The amount is back on your NexisHub balance.",
    },
    "mission_finished_client": {
        "fr": "Le prestataire indique avoir terminé la demande {ref}. Merci de confirmer ou de signaler un problème.",
        "en": "The provider says request {ref} is done. Please confirm or report a problem.",
    },
    "payment_released_client": {
        "fr": "Le paiement de la demande {ref} a été libéré au prestataire.",
        "en": "The payment for request {ref} was released to the provider.",
    },
    "dispute_decision_client": {
        "fr": "NexisHub a pris une décision sur le litige de la demande {ref}.",
        "en": "NexisHub has made a decision on the dispute for request {ref}.",
    },
    "dispute_contested_notify_client": {
        "fr": "La décision sur la demande {ref} a été contestée. L'argent reste bloqué pendant la révision.",
        "en": "The decision on request {ref} was contested. The money stays blocked during the review.",
    },
    "dispute_resolved_refund_client": {
        "fr": "Le litige de la demande {ref} est réglé.",
        "en": "The dispute for request {ref} is settled.",
    },
    "dispute_resolved_release_client": {
        "fr": "Le litige de la demande {ref} est réglé.",
        "en": "The dispute for request {ref} is settled.",
    },
    "dispute_resolved_split_client": {
        "fr": "Le litige de la demande {ref} est réglé.",
        "en": "The dispute for request {ref} is settled.",
    },
    "dispute_offer_accepted_client": {
        "fr": "Le prestataire a accepté votre proposition d'accord pour la demande {ref}.",
        "en": "The provider accepted your settlement offer for request {ref}.",
    },
    "dispute_offer_accepted_client_redo": {
        "fr": "Le prestataire a accepté de repasser pour la demande {ref}.",
        "en": "The provider agreed to come back for request {ref}.",
    },
    "dispute_offer_declined_client": {
        "fr": "Le prestataire a refusé votre proposition d'accord pour la demande {ref}.",
        "en": "The provider declined your settlement offer for request {ref}.",
    },
    "dispute_offer_expired_client": {
        "fr": "Votre proposition d'accord pour la demande {ref} est restée sans réponse.",
        "en": "Your settlement offer for request {ref} received no answer.",
    },
    "presence_question_client": {
        "fr": "Votre prestataire indique être arrivé pour la demande {ref}. Merci de confirmer.",
        "en": "Your provider says they have arrived for request {ref}. Please confirm.",
    },
    "presence_confirmed_client": {
        "fr": "L'arrivée du prestataire est confirmée : la demande {ref} a démarré.",
        "en": "The provider's arrival is confirmed: request {ref} has started.",
    },
    "presence_code_locked_client": {
        "fr": "Le code de présence de la demande {ref} est bloqué après plusieurs codes faux.",
        "en": "The presence code for request {ref} is blocked after several wrong codes.",
    },
    "client_need_accepted": {
        "fr": "NexisHub a répondu à votre besoin {reference}.",
        "en": "NexisHub has answered your request {reference}.",
    },
    "client_need_rejected": {
        "fr": "NexisHub a répondu à votre besoin {reference}.",
        "en": "NexisHub has answered your request {reference}.",
    },
}
MISSION_DEFAULT = {
    "fr": "Il y a du nouveau pour votre demande {ref}.",
    "en": "There is an update on your request {ref}.",
}
DEFAULT = {
    "fr": "Il y a du nouveau sur votre compte.",
    "en": "There is an update on your account.",
}

# Où mène le bouton quand la notification ne nomme pas de demande.
_WALLET_PREFIXES = ("payout_", "payment_")
MENU_MISSIONS = "menu:missions"
MENU_WALLET = "menu:wallet"

# Meta refuse dans une variable : saut de ligne, tabulation, plus de quatre
# espaces de suite.
_UNSAFE = re.compile(r"[\n\r\t]| {5,}")


def template_language(lang: str) -> str:
    return TEMPLATE_LANGUAGE.get(lang, "fr")


def mission_ref(mission_id: int) -> str:
    return f"NXH-{int(mission_id):04d}"


def phrase(message_key: str, params: dict, lang: str) -> str:
    """Phrase `{{1}}` d'une notification, dans la langue du modèle."""
    tpl_lang = template_language(lang)
    mission_id = params.get("mission_id")
    values = {
        "ref": mission_ref(mission_id) if isinstance(mission_id, int) else "",
        "reference": str(params.get("reference") or ""),
    }
    texts = PHRASES.get(message_key)
    if texts is None:
        texts = MISSION_DEFAULT if values["ref"] else DEFAULT
    text = texts[tpl_lang].format(**values)
    return _UNSAFE.sub(" ", text).strip()


def button_payload(message_key: str, params: dict) -> str:
    """Ce que le bouton du modèle ouvre dans la conversation WhatsApp."""
    mission_id = params.get("mission_id")
    if isinstance(mission_id, int):
        return f"mis:{mission_id}"
    if message_key.startswith(_WALLET_PREFIXES):
        return MENU_WALLET
    return MENU_MISSIONS


def components(message_key: str, params: dict, lang: str) -> list[dict]:
    """Paramètres du modèle pour l'API d'envoi de Meta."""
    return [
        {"type": "body", "parameters": [{"type": "text", "text": phrase(message_key, params, lang)}]},
        {
            "type": "button",
            "sub_type": "quick_reply",
            "index": "0",
            "parameters": [{"type": "payload", "payload": button_payload(message_key, params)}],
        },
    ]


def submission(language: str) -> dict:
    """Le modèle au format de création de Meta (POST /{waba}/message_templates)."""
    return {
        "name": TEMPLATE_NAME,
        "language": language,
        "category": CATEGORY,
        "components": [
            {"type": "BODY", "text": BODY[language], "example": {"body_text": [[EXAMPLE[language]]]}},
            {"type": "BUTTONS", "buttons": [{"type": "QUICK_REPLY", "text": BUTTON[language]}]},
        ],
    }


def main() -> None:
    print(json.dumps([submission(language) for language in sorted(BODY)], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
