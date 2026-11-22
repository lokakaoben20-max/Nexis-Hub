"""Extrait de la maquette validée (design/app-accueil-frontend-design.html)
les icônes Phosphor de l'interface et écrit lib/ui/nx_glyphs.dart.

Les icônes « bichromie » (actions rapides) ont une couche à 20 % d'opacité :
une police ne sait pas la porter, d'où ce fichier de tracés dessinés par
lib/ui/nx_icon.dart. Les tracés sont repris tels quels de la maquette.

Usage : python3 outils/icones_interface.py <app-accueil-frontend-design.html> <app-connexion-frontend-design.html>
"""

import re
import sys
from pathlib import Path

# Nom dans la maquette -> nom dans l'app.
ICONES = {
    "p-left": "back",
    "p-search": "search",
    "p-clock": "clock",
    "p-grid": "grid",
    "p-cam": "camera",
    "p-okf": "checkFilled",
    "p-x": "close",
    "q-user": "user",
    "q-dev": "device",
    "q-lang": "language",
    "q-bell": "bell",
    "q-help": "help",
    "q-doc": "document",
    "q-out": "signOut",
    "q-in": "moneyIn",
    "q-outm": "moneyOut",
    "q-shield": "shield",
    "q-undo": "refund",
    "q-id": "idCard",
    "q-devs": "devices",
    "q-aide": "headset",
    "p-serv": "services",
    "p-dep": "deposit",
    "p-ret": "withdraw",
    "p-hist": "history",
    "p-plus": "more",
    "p-home": "home",
    "p-homef": "homeFilled",
    "p-mis": "missions",
    "p-misf": "missionsFilled",
    "p-wal": "wallet",
    "p-walf": "walletFilled",
    "p-usr": "profile",
    "p-usrf": "profileFilled",
    "p-bell": "notification",
    "p-lock": "lock",
    "p-info": "info",
    "p-chev": "chevron",
    "p-eye": "eye",
    "p-eyeo": "eyeOff",
    "p-star": "star",
    "p-alert": "alert",
    "p-ok": "check",
    "p-add": "add",
    "c-seal-check": "sealCheck",
    "sv-peinture": "svcPeinture",
    "sv-demenag": "svcDemenagement",
}


def attr(tag: str, name: str) -> str | None:
    m = re.search(rf'\s{name}="([^"]*)"', tag)
    return m.group(1) if m else None


def main(source: str) -> None:
    html = Path(source).read_text(encoding="utf-8")
    # « c-seal-check » est dans la maquette de connexion, à côté de celle-ci.
    if len(sys.argv) > 2:
        html += Path(sys.argv[2]).read_text(encoding="utf-8")
    lignes = [
        "// Fichier généré par outils/icones_interface.py : ne pas modifier à la main.",
        "// Tracés Phosphor (licence MIT, assets/fonts/LICENSE-Phosphor.txt), viewBox 256.",
        "// Chaque icône = liste de (tracé, opacité).",
        "",
        "const Map<String, List<(String, double)>> nxGlyphs = {",
    ]
    for ancien, nom in ICONES.items():
        m = re.search(rf'<symbol id="{ancien}"[^>]*>(.*?)</symbol>', html, re.S)
        if not m:
            raise SystemExit(f"icône {ancien} introuvable")
        couches = []
        for tag in re.findall(r"<path[^>]*>", m.group(1)):
            d = attr(tag, "d")
            if attr(tag, "fill") == "none" or attr(tag, "stroke") not in (None, "none"):
                raise SystemExit(f"{ancien} : tracé au trait, non pris en charge")
            if attr(tag, "fill-rule") == "evenodd":
                raise SystemExit(f"{ancien} : evenodd, non pris en charge")
            couches.append((d, float(attr(tag, "opacity") or 1)))
        corps = ", ".join(f"('{d}', {o})" for d, o in couches)
        lignes.append(f"  '{nom}': [{corps}],")
    lignes.append("};")
    sortie = Path(__file__).resolve().parent.parent / "lib/ui/nx_glyphs.dart"
    sortie.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print(f"écrit {sortie} ({len(ICONES)} icônes)")


if __name__ == "__main__":
    main(sys.argv[1])
