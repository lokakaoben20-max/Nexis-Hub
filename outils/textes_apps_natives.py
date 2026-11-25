"""Copie les textes de l'app Flutter vers les apps natives iOS et Android.

Source unique : app_mobile/lib/l10n/app_{fr,ln,en}.arb. Les apps natives ne
traduisent rien elles-mêmes : relancer ce script après toute modification
des fichiers .arb.

    python outils/textes_apps_natives.py

Sortie : un fichier textes.json par app, de la forme
    {"cle": {"fr": "...", "ln": "...", "en": "..."}}
Les pluriels ICU ({count, plural, =1{...} other{...}}) deviennent
    {"cle": {"fr": {"=1": "...", "other": "..."}, ...}}
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
SOURCE = RACINE / "app_mobile" / "lib" / "l10n"
LANGUES = ("fr", "ln", "en")
SORTIES = (
    RACINE / "app_ios" / "NexisHub" / "Resources" / "textes.json",
    RACINE / "app_android" / "app" / "src" / "main" / "assets" / "textes.json",
)

_PLURIEL = re.compile(r"^\{(\w+), plural, (.*)\}$", re.DOTALL)


def _formes(corps: str) -> dict[str, str]:
    """Découpe « =1{a} other{b} » en {"=1": "a", "other": "b"}."""
    formes: dict[str, str] = {}
    i = 0
    while i < len(corps):
        if corps[i].isspace():
            i += 1
            continue
        debut = corps.index("{", i)
        nom = corps[i:debut].strip()
        profondeur, j = 0, debut
        while True:
            if corps[j] == "{":
                profondeur += 1
            elif corps[j] == "}":
                profondeur -= 1
                if profondeur == 0:
                    break
            j += 1
        formes[nom] = corps[debut + 1 : j]
        i = j + 1
    if "other" not in formes:
        raise ValueError(f"pluriel sans forme « other » : {corps!r}")
    return formes


def _valeur(texte: str) -> str | dict[str, str]:
    m = _PLURIEL.match(texte)
    return _formes(m.group(2)) if m else texte


def construire() -> dict[str, dict[str, object]]:
    arb = {
        langue: json.loads((SOURCE / f"app_{langue}.arb").read_text("utf-8"))
        for langue in LANGUES
    }
    cles = [c for c in arb["fr"] if not c.startswith("@")]
    textes: dict[str, dict[str, object]] = {}
    for cle in cles:
        manquantes = [lg for lg in LANGUES if cle not in arb[lg]]
        if manquantes:
            raise SystemExit(f"« {cle} » manque en : {', '.join(manquantes)}")
        textes[cle] = {lg: _valeur(arb[lg][cle]) for lg in LANGUES}
    return textes


def main() -> int:
    contenu = json.dumps(construire(), ensure_ascii=False, indent=1, sort_keys=True)
    for sortie in SORTIES:
        sortie.parent.mkdir(parents=True, exist_ok=True)
        sortie.write_text(contenu + "\n", "utf-8")
        print(f"écrit : {sortie.relative_to(RACINE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
