"""Logo écrit Nexis Hub (piste 1 choisie par Ben le 2026-11-25).

« NEXIS » en Unbounded 700, dont le E est celui de l'icône de l'app (trois barres
biseautées, mêmes proportions : barres de 104, espaces de 108, biseau de 62 sur
528), puis « HUB » en Unbounded 300 sur la même ligne. Les lettres sont
vectorisées depuis la police de l'app : le logo ne dépend d'aucune police au
moment de l'affichage.

Écrit :
- docs/marque/logo-nexis-hub-blanc.svg et logo-nexis-hub-bleu.svg ;
- app_ios/NexisHub/Resources/Assets.xcassets/LogoBlanc.imageset (SVG vectoriel) ;
- app_android/app/src/main/res/drawable/logo_blanc.xml (VectorDrawable).

Usage : python3 outils/logo_nexis.py   (depuis la racine du dépôt ; demande
fonttools et uharfbuzz)
"""
from __future__ import annotations

import json
import pathlib

import uharfbuzz as hb
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

RACINE = pathlib.Path(__file__).resolve().parent.parent
POLICE = RACINE / "app_android/app/src/main/res/font/unbounded.ttf"
BLEU = "#0A63F0"

CAPITALE = 750  # hauteur des capitales d'Unbounded (OS/2 sCapHeight), pour 1000 unités
MARGE_E = 50  # 0,05 em de chaque côté du E, comme sur la maquette
ESPACE_HUB = 280  # 0,28 em entre NEXIS et HUB


def _police(graisse: int) -> hb.Font:
    face = hb.Face(POLICE.read_bytes())
    font = hb.Font(face)
    font.set_variations({"wght": graisse})
    return font


_INSTANCES: dict[int, object] = {}


def _glyphes(graisse: int):
    """Contours de la police figée à cette graisse (instance statique fontTools)."""
    if graisse not in _INSTANCES:
        statique = instantiateVariableFont(TTFont(POLICE), {"wght": graisse})
        _INSTANCES[graisse] = (statique.getGlyphSet(), statique.getGlyphOrder())
    return _INSTANCES[graisse]


def _texte(pen: RecordingPen, texte: str, graisse: int, x: float) -> float:
    """Dessine le texte à partir de x (ligne de base y = 0) ; renvoie le x de fin.

    HarfBuzz place les lettres (approches et crénage à cette graisse) ;
    fontTools fournit les contours de l'instance statique."""
    font = _police(graisse)
    jeu, ordre = _glyphes(graisse)
    buf = hb.Buffer()
    buf.add_str(texte)
    buf.guess_segment_properties()
    hb.shape(font, buf, {"kern": True})
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        jeu[ordre[info.codepoint]].draw(TransformPen(pen, (1, 0, 0, 1, x + pos.x_offset, pos.y_offset)))
        x += pos.x_advance
    return x


def _e_icone(pen: RecordingPen, x: float) -> float:
    """Le E de l'icône, haut comme une capitale ; renvoie le x de fin."""
    f = CAPITALE / 528
    x0 = x + MARGE_E
    for haut in (0, 212, 424):  # en unités de l'icône, depuis le haut
        y1, y2 = CAPITALE - haut * f, CAPITALE - (haut + 104) * f
        pen.moveTo((x0, y1))
        pen.lineTo((x0 + 498 * f, y1))
        pen.lineTo((x0 + 436 * f, y2))
        pen.lineTo((x0, y2))
        pen.closePath()
    return x0 + 498 * f + MARGE_E


def dessin() -> tuple[str, float, float]:
    """Chemin SVG (y vers le bas, origine en haut à gauche), largeur, hauteur."""
    pen = RecordingPen()
    x = _texte(pen, "N", 700, 0)
    x = _e_icone(pen, x)
    x = _texte(pen, "XIS", 700, x)
    _texte(pen, "HUB", 300, x + ESPACE_HUB)
    bornes = BoundsPen(None)
    pen.replay(bornes)
    xmin, ymin, xmax, ymax = bornes.bounds
    svg = SVGPathPen(None, ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
    pen.replay(TransformPen(svg, (1, 0, 0, -1, -xmin, ymax)))
    return svg.getCommands(), xmax - xmin, ymax - ymin


def main() -> None:
    chemin, largeur, hauteur = dessin()
    l, h = f"{largeur:.0f}", f"{hauteur:.0f}"

    def svg(couleur: str) -> str:
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {l} {h}" width="{l}" height="{h}" '
                f'role="img" aria-label="Nexis Hub"><path fill="{couleur}" d="{chemin}"/></svg>\n')

    marque = RACINE / "docs/marque"
    marque.mkdir(parents=True, exist_ok=True)
    (marque / "logo-nexis-hub-blanc.svg").write_text(svg("#FFFFFF"))
    (marque / "logo-nexis-hub-bleu.svg").write_text(svg(BLEU))

    imageset = RACINE / "app_ios/NexisHub/Resources/Assets.xcassets/LogoBlanc.imageset"
    for ancien in imageset.glob("*.png"):
        ancien.unlink()
    (imageset / "LogoBlanc.svg").write_text(svg("#FFFFFF"))
    (imageset / "Contents.json").write_text(json.dumps({
        "images": [{"filename": "LogoBlanc.svg", "idiom": "universal"}],
        "info": {"author": "xcode", "version": 1},
        "properties": {"preserves-vector-representation": True, "template-rendering-intent": "original"},
    }, indent=2) + "\n")

    res = RACINE / "app_android/app/src/main/res/drawable"
    (res / "logo_blanc.png").unlink(missing_ok=True)
    (res / "logo_blanc.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<!-- Généré par outils/logo_nexis.py : ne pas modifier à la main. -->\n"
        '<vector xmlns:android="http://schemas.android.com/apk/res/android"\n'
        f'    android:width="{largeur / hauteur * 24:.1f}dp"\n'
        '    android:height="24dp"\n'
        f'    android:viewportWidth="{l}"\n'
        f'    android:viewportHeight="{h}">\n'
        f'    <path android:fillColor="#FFFFFFFF" android:pathData="{chemin}" />\n'
        "</vector>\n")
    print(f"Logo : {l} × {h} unités (rapport {largeur / hauteur:.2f})")


if __name__ == "__main__":
    main()
