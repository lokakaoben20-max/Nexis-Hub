import 'package:flutter_test/flutter_test.dart';
import 'package:nexis_hub/ui/nx_glyphs.dart';
import 'package:nexis_hub/ui/nx_icon.dart';

void main() {
  test('toutes les icônes de la maquette se lisent et tiennent dans 256', () {
    expect(nxGlyphs, isNotEmpty);
    nxGlyphs.forEach((name, layers) {
      expect(layers, isNotEmpty, reason: name);
      for (final (d, opacity) in layers) {
        final path = parseSvgPath(d);
        expect(path.getBounds().isEmpty, isFalse, reason: name);
        // Bornes réelles du dessin (getBounds donne celles des points de
        // contrôle, plus larges pour les arcs).
        var n = 0;
        for (final metric in path.computeMetrics()) {
          for (var t = 0.0; t <= metric.length; t += 1) {
            final p = metric.getTangentForOffset(t)!.position;
            n++;
            expect(p.dx, inInclusiveRange(-1, 257), reason: '$name $p');
            expect(p.dy, inInclusiveRange(-1, 257), reason: '$name $p');
          }
        }
        expect(n, greaterThan(10), reason: name);
        expect(opacity, inInclusiveRange(0, 1));
      }
    });
  });

  test('le lecteur de tracés gère relatif, abrégé et arcs', () {
    // Carré tracé en relatif avec H/V.
    final square = parseSvgPath('M10 10h20v20H10z');
    expect(square.getBounds().width, 20);
    expect(square.getBounds().height, 20);
    // Demi-cercle par arc : de (0,0) à (20,0), rayon 10.
    final arc = parseSvgPath('M0 0a10,10,0,0,1,20,0z');
    expect(arc.getBounds().width, closeTo(20, .01));
    expect(arc.getBounds().height, closeTo(10, .01));
    // Drapeaux collés au nombre suivant (« 0,01-5 » en SVG compact).
    final compact = parseSvgPath('M0 0a5 5 0 01-10 0z');
    expect(compact.getBounds().width, closeTo(10, .01));
    // Nombres collés : « .5.5 » = 0.5 puis 0.5.
    final dots = parseSvgPath('M.5.5L1.5.5');
    expect(dots.getBounds().width, closeTo(1, .001));
  });

  test('un tracé invalide est refusé', () {
    expect(() => parseSvgPath('M10'), throwsFormatException);
    expect(() => parseSvgPath('X1 2'), throwsFormatException);
  });
}
