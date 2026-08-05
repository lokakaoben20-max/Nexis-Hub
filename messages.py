# ═══════════════════════════════════════════════════════
# NEXIS HUB — Messages Système Officiels
# Français / Lingala / English
#
# Les textes ne sont plus dans ce fichier : ils vivent dans
# translations/fr.json, translations/ln.json et translations/en.json.
# Pour corriger une traduction, ouvrez le fichier .json de la langue
# concernée avec n'importe quel éditeur de texte, modifiez le texte
# entre guillemets, enregistrez, puis relancez le bot.
#
# Règles à respecter en éditant un .json :
#   - ne changez pas les noms de clés (à gauche des deux-points)
#   - gardez les {placeholders} (ex. {mission_id}) tels quels
#   - \n = saut de ligne, les balises <b></b> mettent en gras
# ═══════════════════════════════════════════════════════

import json
from pathlib import Path

TRANSLATIONS_DIR = Path(__file__).with_name("translations")
LANGUAGES = ("fr", "ln", "en")


def _load_translations() -> dict[str, dict[str, str]]:
    translations = {}
    for lang in LANGUAGES:
        path = TRANSLATIONS_DIR / f"{lang}.json"
        translations[lang] = json.loads(path.read_text(encoding="utf-8"))
    return translations


MESSAGES = _load_translations()


def get_message(key: str, lang: str = "fr", **kwargs) -> str:
    """
    Récupère un message dans la bonne langue.
    Si la clé n'existe pas dans la langue choisie,
    retourne le message en français par défaut.
    """
    msg = MESSAGES.get(lang, MESSAGES["fr"]).get(
        key,
        MESSAGES["fr"].get(key, f"[Message manquant : {key}]")
    )
    if kwargs:
        try:
            return msg.format(**kwargs)
        except KeyError:
            return msg
    return msg
