import 'dart:math' as math;

import 'package:flutter/widgets.dart';

import 'nx_glyphs.dart';

/// Icône Phosphor de l'interface, dessinée depuis les tracés de la maquette
/// validée (lib/ui/nx_glyphs.dart, généré). Même dessin, même couleur de
/// remplissage que la maquette, y compris la couche à 20 % des actions.
class NxIcon extends StatelessWidget {
  const NxIcon(this.name, {super.key, this.size = 24, this.color});

  final String name;
  final double size;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final layers = nxGlyphs[name];
    assert(layers != null, 'Icône inconnue : $name');
    final tint =
        color ?? IconTheme.of(context).color ?? const Color(0xFF000000);
    return ExcludeSemantics(
      child: SizedBox(
        width: size,
        height: size,
        child: CustomPaint(painter: _NxIconPainter(name, tint)),
      ),
    );
  }
}

final Map<String, List<(Path, double)>> _cache = {};

List<(Path, double)> _paths(String name) => _cache.putIfAbsent(
  name,
  () => [
    for (final (d, opacity) in nxGlyphs[name]!) (parseSvgPath(d), opacity),
  ],
);

class _NxIconPainter extends CustomPainter {
  _NxIconPainter(this.name, this.color);

  final String name;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    canvas.save();
    canvas.scale(size.width / 256, size.height / 256);
    for (final (path, opacity) in _paths(name)) {
      canvas.drawPath(
        path,
        Paint()
          ..style = PaintingStyle.fill
          ..isAntiAlias = true
          ..color = color.withValues(alpha: color.a * opacity),
      );
    }
    canvas.restore();
  }

  @override
  bool shouldRepaint(_NxIconPainter old) =>
      old.name != name || old.color != color;
}

/// Lit un tracé SVG (commandes M L H V C S Q T A Z, absolues et relatives).
/// Public pour les tests.
Path parseSvgPath(String d) {
  final path = Path();
  var i = 0;
  var cmd = '';
  var x = 0.0, y = 0.0, sx = 0.0, sy = 0.0;
  double? cx, cy; // dernier point de contrôle (courbes lisses)
  var prev = '';

  bool isSpace(int c) => c == 0x20 || c == 0x2c || c == 0x0a || c == 0x09;
  void skip() {
    while (i < d.length && isSpace(d.codeUnitAt(i))) {
      i++;
    }
  }

  double number() {
    skip();
    final start = i;
    if (i < d.length && (d[i] == '-' || d[i] == '+')) i++;
    var dot = false;
    while (i < d.length) {
      final c = d.codeUnitAt(i);
      if (c >= 0x30 && c <= 0x39) {
        i++;
      } else if (c == 0x2e && !dot) {
        dot = true;
        i++;
      } else if ((c == 0x65 || c == 0x45) && i > start) {
        i++;
        if (i < d.length && (d[i] == '-' || d[i] == '+')) i++;
      } else {
        break;
      }
    }
    if (i == start) throw FormatException('Nombre attendu', d, i);
    return double.parse(d.substring(start, i));
  }

  bool flag() {
    skip();
    final c = d[i++];
    if (c != '0' && c != '1') throw FormatException('Drapeau attendu', d, i);
    return c == '1';
  }

  while (true) {
    skip();
    if (i >= d.length) break;
    final c = d[i];
    if (RegExp('[A-Za-z]').hasMatch(c)) {
      cmd = c;
      i++;
    } else if (cmd.isEmpty) {
      throw FormatException('Commande attendue', d, i);
    } else if (cmd == 'M') {
      cmd = 'L';
    } else if (cmd == 'm') {
      cmd = 'l';
    }
    final rel = cmd == cmd.toLowerCase();
    final up = cmd.toUpperCase();
    switch (up) {
      case 'Z':
        path.close();
        x = sx;
        y = sy;
        cx = cy = null;
      case 'M':
        final nx = number() + (rel ? x : 0), ny = number() + (rel ? y : 0);
        path.moveTo(nx, ny);
        x = sx = nx;
        y = sy = ny;
        cx = cy = null;
      case 'L':
        final nx = number() + (rel ? x : 0), ny = number() + (rel ? y : 0);
        path.lineTo(nx, ny);
        x = nx;
        y = ny;
        cx = cy = null;
      case 'H':
        x = number() + (rel ? x : 0);
        path.lineTo(x, y);
        cx = cy = null;
      case 'V':
        y = number() + (rel ? y : 0);
        path.lineTo(x, y);
        cx = cy = null;
      case 'C':
        final x1 = number() + (rel ? x : 0), y1 = number() + (rel ? y : 0);
        final x2 = number() + (rel ? x : 0), y2 = number() + (rel ? y : 0);
        final nx = number() + (rel ? x : 0), ny = number() + (rel ? y : 0);
        path.cubicTo(x1, y1, x2, y2, nx, ny);
        cx = x2;
        cy = y2;
        x = nx;
        y = ny;
      case 'S':
        final smooth = 'CS'.contains(prev.toUpperCase()) && prev.isNotEmpty;
        final x1 = smooth ? 2 * x - cx! : x, y1 = smooth ? 2 * y - cy! : y;
        final x2 = number() + (rel ? x : 0), y2 = number() + (rel ? y : 0);
        final nx = number() + (rel ? x : 0), ny = number() + (rel ? y : 0);
        path.cubicTo(x1, y1, x2, y2, nx, ny);
        cx = x2;
        cy = y2;
        x = nx;
        y = ny;
      case 'Q':
        final x1 = number() + (rel ? x : 0), y1 = number() + (rel ? y : 0);
        final nx = number() + (rel ? x : 0), ny = number() + (rel ? y : 0);
        path.quadraticBezierTo(x1, y1, nx, ny);
        cx = x1;
        cy = y1;
        x = nx;
        y = ny;
      case 'T':
        final smooth = 'QT'.contains(prev.toUpperCase()) && prev.isNotEmpty;
        final x1 = smooth ? 2 * x - cx! : x, y1 = smooth ? 2 * y - cy! : y;
        final nx = number() + (rel ? x : 0), ny = number() + (rel ? y : 0);
        path.quadraticBezierTo(x1, y1, nx, ny);
        cx = x1;
        cy = y1;
        x = nx;
        y = ny;
      case 'A':
        final rx = number(), ry = number(), rot = number();
        final large = flag(), sweep = flag();
        final nx = number() + (rel ? x : 0), ny = number() + (rel ? y : 0);
        if (rx == 0 || ry == 0 || (nx == x && ny == y)) {
          path.lineTo(nx, ny);
        } else {
          path.arcToPoint(
            Offset(nx, ny),
            radius: Radius.elliptical(rx.abs(), ry.abs()),
            rotation: rot * math.pi / 180,
            largeArc: large,
            clockwise: sweep,
          );
        }
        x = nx;
        y = ny;
        cx = cy = null;
      default:
        throw FormatException('Commande inconnue $cmd', d, i);
    }
    prev = cmd;
  }
  return path;
}
