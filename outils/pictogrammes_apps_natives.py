"""Copie les pictogrammes de services dans les apps natives iOS et Android.

Source : Phosphor Icons (duotone, licence MIT) et Tabler Icons (trait,
licence MIT), installés avec npm :

    npm install @phosphor-icons/core @tabler/icons
    python outils/pictogrammes_apps_natives.py <dossier node_modules>

La liste des services et de leurs objets vit dans SERVICES : le premier
objet est l'icône principale, les suivants forment le tour animé.
Les apps lisent la même liste (Pictogrammes.swift et Pictogrammes.kt) :
les garder synchronisées.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
CATALOGUE_IOS = RACINE / "app_ios" / "NexisHub" / "Resources" / "Pictogrammes.xcassets"
DRAWABLE_ANDROID = RACINE / "app_android" / "app" / "src" / "main" / "res" / "drawable"

# Service : icône principale, puis les objets du tour (choix de Ben, 2026-11-25).
SERVICES: dict[str, list[str]] = {
    "plomberie": ["ph:wrench", "ph:pipe", "ph:shower", "ph:toilet"],
    "electricite": ["ph:lightning", "ph:plug", "ph:lightbulb", "ph:power"],
    "climatisation": ["ph:snowflake", "ph:fan", "ph:wind", "ph:thermometer"],
    "informatique": ["ph:laptop", "ph:monitor", "ph:printer", "ph:wifi-high"],
    "graphisme": ["ph:pen-nib", "ph:palette", "ph:paint-brush", "ph:image"],
    "coiffure": ["ph:scissors", "tb:razor-electric", "ph:hair-dryer", "ph:armchair"],
    "nettoyage": ["ph:broom", "ph:spray-bottle", "ph:washing-machine", "ph:hand-soap"],
    "jardinage": ["ph:plant", "ph:flower", "ph:tree-palm", "ph:shovel"],
    "autre": ["ph:squares-four"],
    "peinture": [
        "ph:paint-roller",
        "ph:paint-bucket",
        "ph:palette",
        "ph:paint-brush-household",
    ],
    "demenagement": ["ph:truck", "ph:package", "ph:key", "ph:truck-trailer"],
}


def nom(icone: str) -> str:
    """« ph:pen-nib » → « ph_pen_nib » (nom d'image iOS et de ressource Android)."""
    return icone.replace(":", "_").replace("-", "_")


def source(modules: Path, icone: str) -> str:
    biblio, n = icone.split(":")
    if biblio == "ph":
        return (
            modules / "@phosphor-icons/core/assets/duotone" / f"{n}-duotone.svg"
        ).read_text()
    return (modules / "@tabler/icons/icons/outline" / f"{n}.svg").read_text()


def svg_ios(texte: str, icone: str) -> str:
    """SVG autonome en noir : iOS le teinte (rendu « template »)."""
    texte = re.sub(r"\s+", " ", texte).strip()
    texte = re.sub(r'\s(class|width|height)="[^"]*"', "", texte)
    texte = texte.replace("currentColor", "#000000")
    texte = texte.replace("<svg ", '<svg width="24" height="24" ', 1)
    if icone.startswith("tb:"):
        texte = texte.replace('stroke-width="2"', 'stroke-width="1.6"')
        texte = texte.replace(
            '<path stroke="none" d="M0 0h24v24H0z" fill="none" />', ""
        )
    return texte


def vecteur_android(texte: str, icone: str) -> str:
    """VectorDrawable : noir, teinté dans l'app ; la partie claire du duotone
    garde son opacité de 20 %."""
    chemins = re.findall(r"<path([^>]*)/>", re.sub(r"\s+", " ", texte))
    lignes = []
    for attributs in chemins:
        d = re.search(r'\sd="([^"]+)"', attributs).group(1)
        if icone.startswith("tb:"):
            if 'stroke="none"' in attributs:
                continue
            lignes.append(
                f'    <path android:pathData="{d}" android:strokeColor="#FF000000" '
                'android:strokeWidth="1.6" android:strokeLineCap="round" '
                'android:strokeLineJoin="round" android:fillColor="#00000000" />'
            )
        else:
            alpha = ' android:fillAlpha="0.2"' if 'opacity="0.2"' in attributs else ""
            lignes.append(
                f'    <path android:pathData="{d}" android:fillColor="#FF000000"{alpha} />'
            )
    taille = 24 if icone.startswith("tb:") else 256
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f"<!-- {icone} : Phosphor Icons / Tabler Icons, licence MIT -->\n"
        '<vector xmlns:android="http://schemas.android.com/apk/res/android"\n'
        '    android:width="24dp" android:height="24dp"\n'
        f'    android:viewportWidth="{taille}" android:viewportHeight="{taille}">\n'
        + "\n".join(lignes)
        + "\n</vector>\n"
    )


def main(modules: Path) -> int:
    icones = sorted({i for liste in SERVICES.values() for i in liste})
    CATALOGUE_IOS.mkdir(parents=True, exist_ok=True)
    (CATALOGUE_IOS / "Contents.json").write_text(
        json.dumps({"info": {"author": "xcode", "version": 1}}, indent=2) + "\n"
    )
    DRAWABLE_ANDROID.mkdir(parents=True, exist_ok=True)
    for icone in icones:
        texte = source(modules, icone)
        jeu = CATALOGUE_IOS / f"{nom(icone)}.imageset"
        jeu.mkdir(exist_ok=True)
        (jeu / f"{nom(icone)}.svg").write_text(svg_ios(texte, icone) + "\n")
        (jeu / "Contents.json").write_text(
            json.dumps(
                {
                    "images": [{"filename": f"{nom(icone)}.svg", "idiom": "universal"}],
                    "info": {"author": "xcode", "version": 1},
                    "properties": {
                        "preserves-vector-representation": True,
                        "template-rendering-intent": "template",
                    },
                },
                indent=2,
            )
            + "\n"
        )
        (DRAWABLE_ANDROID / f"{nom(icone)}.xml").write_text(
            vecteur_android(texte, icone)
        )
    print(f"{len(icones)} pictogrammes écrits pour iOS et Android")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "usage : python outils/pictogrammes_apps_natives.py <node_modules>"
        )
    sys.exit(main(Path(sys.argv[1])))
