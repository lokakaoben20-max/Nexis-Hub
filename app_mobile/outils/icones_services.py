"""Fabrique la police des icônes de services Nexis (série finale choisie
par Ben, design/icones-services.html) : assets/fonts/NexisServices.ttf.

Les traits (climatisation) sont convertis en surfaces et les règles
« evenodd » ramenées au remplissage normal, pour que la police rende
exactement les dessins de la maquette.

Usage : python3 outils/icones_services.py <chemin de icones-services.html>
"""

import re
import sys
from pathlib import Path

import pathops
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.svgLib.path import parse_path

# Ordre = points de code à partir de U+E000 (repris dans lib/ui/icons.dart).
ICONES = [
    "plomberie",
    "electricite",
    "clim",
    "info",
    "graph",
    "coiffure",
    "nettoyage",
    "jardin",
    "autre",
]
EM = 256


def attr(tag: str, name: str) -> str | None:
    m = re.search(rf'\s{name}="([^"]*)"', tag)
    return m.group(1) if m else None


def symbole(html: str, nom: str) -> pathops.Path:
    m = re.search(rf'<symbol id="f-{nom}"[^>]*>(.*?)</symbol>', html, re.S)
    if not m:
        raise SystemExit(f"icône f-{nom} introuvable")
    total = pathops.Path()
    for tag in re.findall(r"<path[^>]*>", m.group(1)):
        p = pathops.Path()
        parse_path(attr(tag, "d"), p.getPen())
        if attr(tag, "fill-rule") == "evenodd":
            p.fillType = pathops.FillType.EVEN_ODD
        if attr(tag, "fill") == "none":
            p.stroke(
                float(attr(tag, "stroke-width") or 1),
                pathops.LineCap.ROUND_CAP,
                pathops.LineJoin.ROUND_JOIN,
                4,
            )
        p.convertConicsToQuads()
        p.simplify()
        total = pathops.op(total, p, pathops.PathOp.UNION)
    total.simplify(fix_winding=True)
    return total


def main(source: str) -> None:
    html = Path(source).read_text(encoding="utf-8")
    noms = [".notdef"] + [f"nx_{n}" for n in ICONES]
    glyphes, cmap = {".notdef": TTGlyphPen(None).glyph()}, {}
    for i, nom in enumerate(ICONES):
        pen = TTGlyphPen(None)
        # SVG : y vers le bas ; police : y vers le haut.
        symbole(html, nom).draw(
            TransformPen(Cu2QuPen(pen, 0.5, reverse_direction=True), (1, 0, 0, -1, 0, EM))
        )
        glyphes[f"nx_{nom}"] = pen.glyph()
        cmap[0xE000 + i] = f"nx_{nom}"

    fb = FontBuilder(EM, isTTF=True)
    fb.setupGlyphOrder(noms)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphes)
    fb.setupHorizontalMetrics({n: (EM, 0) for n in noms})
    fb.setupHorizontalHeader(ascent=EM, descent=0)
    fb.setupOS2(sTypoAscender=EM, sTypoDescender=0, usWinAscent=EM, usWinDescent=0)
    fb.setupNameTable({"familyName": "NexisServices", "styleName": "Regular"})
    fb.setupPost()
    sortie = Path(__file__).resolve().parent.parent / "assets/fonts/NexisServices.ttf"
    fb.save(sortie)
    print(f"écrit {sortie}")


if __name__ == "__main__":
    main(sys.argv[1])
