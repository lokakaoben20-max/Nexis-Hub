"""Garde-fou i18n : toute clé utilisée dans le code existe dans les 3 langues.

Ce test existe à cause d'un bug réel trouvé le 2026-08-07 : 11 clés du parcours
d'inscription et de création de mission (`ask_client_phone`, `phone_required`,
`mission_saved`, `provider_registered`…) n'existaient **que** dans `ln.json`. Comme
`get_message` retombe sur le français quand une clé manque, et que le français lui-même
ne l'avait pas, un client francophone ou anglophone voyait littéralement
`[Message manquant : ask_client_phone]` au premier écran d'inscription.

Une simple parité de clés entre fichiers ne suffirait pas : le projet contient une
dizaine de clés mortes présentes seulement en français, qui feraient échouer le test
sans qu'aucun utilisateur ne soit affecté. On vérifie donc les clés **réellement
appelées** via `get_message("...")`, en parsant l'AST plutôt qu'avec une regex (les
appels avec une clé variable, comme dans `backend/app/tasks.py`, sont ignorés : leur
valeur n'est pas connue statiquement).
"""

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from messages import LANGUAGES, MESSAGES

# Fichiers qui rendent du texte à un utilisateur final.
SOURCE_FILES = [
    ROOT / "main.py",
    *sorted((ROOT / "telegram_bot").glob("*.py")),
    *sorted((ROOT / "backend" / "app").glob("*.py")),
]


def _literal_message_keys(path: Path) -> set[str]:
    """Clés passées en littéral à get_message() dans ce fichier."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    keys = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if name != "get_message" or not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            keys.add(first.value)
    return keys


def _used_keys_by_file() -> dict[Path, set[str]]:
    return {path: _literal_message_keys(path) for path in SOURCE_FILES if path.exists()}


@pytest.mark.parametrize("lang", LANGUAGES)
def test_every_used_message_key_exists_in_language(lang):
    missing = {}
    for path, keys in _used_keys_by_file().items():
        absent = sorted(key for key in keys if key not in MESSAGES[lang])
        if absent:
            missing[path.relative_to(ROOT).as_posix()] = absent

    assert not missing, (
        f"Clés utilisées dans le code mais absentes de translations/{lang}.json : {missing}. "
        f"Un utilisateur en '{lang}' verrait '[Message manquant : ...]' à l'écran."
    )


def test_at_least_one_key_is_actually_scanned():
    """Sans ça, une régression du parseur AST rendrait le test ci-dessus toujours vert."""
    total = sum(len(keys) for keys in _used_keys_by_file().values())
    assert total > 50, f"Seulement {total} clés détectées — le scan AST est probablement cassé."
