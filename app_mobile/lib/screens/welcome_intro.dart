import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../data/models.dart';
import '../ui/common.dart';
import '../ui/icons.dart';
import '../ui/theme.dart';

/// Pièces animées de l'écran de bienvenue (piste A retenue par Ben le
/// 2026-11-20, design/bienvenue/bienvenue-pistes.html) : le logo dont les
/// barres s'assemblent, NEXIS HUB lettre par lettre, les métiers en
/// orbite, le fond qui respire et le reflet sur « Commencer ».
///
/// L'entrée dure environ 1,5 s. Quand le téléphone demande moins
/// d'animations, tout s'affiche directement dans son état final.

/// Une valeur de 0 à 1 entre [start] et [end] secondes de l'entrée.
double introStep(double seconds, double start, double end) {
  if (seconds <= start) return 0;
  if (seconds >= end) return 1;
  return Curves.easeOutCubic.transform((seconds - start) / (end - start));
}

/// Le monogramme : trois barres qui arrivent de la gauche l'une après
/// l'autre (mêmes proportions que le logo, viewBox 513 487 973 1026).
class AssemblingMonogram extends StatelessWidget {
  const AssemblingMonogram({super.key, required this.seconds, this.width = 58});

  final double seconds;
  final double width;

  @override
  Widget build(BuildContext context) => SizedBox(
    width: width,
    height: width * 1026 / 973,
    child: CustomPaint(painter: _MonogramPainter(seconds)),
  );
}

class _MonogramPainter extends CustomPainter {
  _MonogramPainter(this.seconds);

  final double seconds;

  @override
  void paint(Canvas canvas, Size size) {
    final sx = size.width / 973, sy = size.height / 1026;
    for (var i = 0; i < 3; i++) {
      final t = introStep(seconds, i * .09, .5 + i * .09);
      if (t == 0) continue;
      final top = 413.0 * i;
      final dx = -(1 - t) * .46 * 973;
      final path = Path()
        ..moveTo(dx * sx, top * sy)
        ..lineTo((973 + dx) * sx, top * sy)
        ..lineTo((851 + dx) * sx, (top + 200) * sy)
        ..lineTo(dx * sx, (top + 200) * sy)
        ..close();
      canvas.drawPath(path, Paint()..color = Colors.white.withValues(alpha: t));
    }
  }

  @override
  bool shouldRepaint(_MonogramPainter old) => old.seconds != seconds;
}

/// NEXIS HUB, lettre par lettre.
class SpelledBrand extends StatelessWidget {
  const SpelledBrand({super.key, required this.seconds});

  final double seconds;

  @override
  Widget build(BuildContext context) {
    const word = 'NEXIS HUB';
    return Semantics(
      label: 'Nexis Hub',
      excludeSemantics: true,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          for (var i = 0; i < word.length; i++)
            Builder(
              builder: (context) {
                final t = introStep(seconds, .38 + i * .04, .68 + i * .04);
                return Opacity(
                  opacity: t,
                  child: Transform.translate(
                    offset: Offset(0, 6 * (1 - t)),
                    child: Text(
                      word[i],
                      style: title(
                        12,
                        color: Colors.white.withValues(alpha: .92),
                      ).copyWith(letterSpacing: 3.1),
                    ),
                  ),
                );
              },
            ),
        ],
      ),
    );
  }
}

/// Fondu qui monte de quelques pixels.
class IntroFade extends StatelessWidget {
  const IntroFade({
    super.key,
    required this.seconds,
    required this.start,
    required this.end,
    required this.child,
    this.rise = 8,
  });

  final double seconds;
  final double start;
  final double end;
  final double rise;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final t = introStep(seconds, start, end);
    return Opacity(
      opacity: t,
      child: Transform.translate(
        offset: Offset(0, rise * (1 - t)),
        child: child,
      ),
    );
  }
}

/// Les huit métiers en orbite autour du bouclier. [turn] avance de 0 à 1
/// en continu (un tour lent) ; [seconds] règle l'apparition.
class ServiceOrbit extends StatelessWidget {
  const ServiceOrbit({super.key, required this.seconds, required this.turn});

  final double seconds;
  final double turn;

  static const _inner = [
    Service.plomberie,
    Service.electricite,
    Service.climatisation,
  ];
  static const _outer = [
    Service.informatique,
    Service.graphisme,
    Service.coiffure,
    Service.nettoyage,
    Service.jardinage,
  ];

  @override
  Widget build(BuildContext context) {
    return ExcludeSemantics(
      child: SizedBox(
        width: 190,
        height: 190,
        child: Stack(
          clipBehavior: Clip.none,
          alignment: Alignment.center,
          children: [
            const CustomPaint(size: Size(190, 190), painter: _RingsPainter()),
            ..._satellites(_inner, 46, -90, turn, 0),
            ..._satellites(_outer, 76, -60, -turn * 38 / 52, 3),
            Container(
              width: 46,
              height: 46,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: Colors.white.withValues(alpha: .95),
                boxShadow: [
                  BoxShadow(
                    color: Colors.white.withValues(alpha: .07),
                    spreadRadius: 16,
                  ),
                  BoxShadow(
                    color: Colors.white.withValues(alpha: .14),
                    spreadRadius: 7,
                  ),
                ],
              ),
              child: const Icon(
                PhRegular.shieldCheck,
                size: 23,
                color: NexisColors.brand,
              ),
            ),
          ],
        ),
      ),
    );
  }

  List<Widget> _satellites(
    List<Service> services,
    double radius,
    double offsetDeg,
    double turns,
    int first,
  ) => [
    for (var k = 0; k < services.length; k++)
      Builder(
        builder: (context) {
          final angle =
              (k / services.length * 360 + offsetDeg) * math.pi / 180 +
              turns * 2 * math.pi;
          final t = introStep(
            seconds,
            .75 + (first + k) * .06,
            1.15 + (first + k) * .06,
          );
          final visual = serviceVisual(services[k]);
          return Transform.translate(
            offset: Offset(math.cos(angle) * radius, math.sin(angle) * radius),
            child: Opacity(
              opacity: t,
              child: Transform.scale(
                scale: .2 + .8 * Curves.easeOutBack.transform(t),
                child: Container(
                  width: 32,
                  height: 32,
                  decoration: const BoxDecoration(
                    shape: BoxShape.circle,
                    color: Colors.white,
                    boxShadow: [
                      BoxShadow(
                        color: Color(0x73021937),
                        offset: Offset(0, 6),
                        blurRadius: 14,
                        spreadRadius: -6,
                      ),
                    ],
                  ),
                  child: Icon(visual.icon, size: 16, color: visual.color),
                ),
              ),
            ),
          );
        },
      ),
  ];
}

class _RingsPainter extends CustomPainter {
  const _RingsPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final c = size.center(Offset.zero);
    canvas.drawCircle(
      c,
      76,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1
        ..color = Colors.white.withValues(alpha: .18),
    );
    // Cercle intérieur en pointillés.
    final dash = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1
      ..color = Colors.white.withValues(alpha: .32);
    const r = 46.0, segments = 36;
    for (var i = 0; i < segments; i++) {
      final a = i / segments * 2 * math.pi;
      canvas.drawArc(
        Rect.fromCircle(center: c, radius: r),
        a,
        math.pi / segments,
        false,
        dash,
      );
    }
  }

  @override
  bool shouldRepaint(_RingsPainter old) => false;
}

/// Fond bleu de la maquette, avec une lueur qui « respire » ([breath]
/// va de 0 à 1 et revient).
class BreathingBackground extends StatelessWidget {
  const BreathingBackground({
    super.key,
    required this.breath,
    required this.child,
  });

  final double breath;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final b = Curves.easeInOut.transform(breath);
    return DecoratedBox(
      decoration: const BoxDecoration(
        gradient: RadialGradient(
          center: Alignment(0, -.4),
          radius: 1.1,
          colors: [
            Color(0xFF2E9BFF),
            Color(0xFF0A8CFF),
            Color(0xFF0870EE),
            NexisColors.brand,
          ],
          stops: [0, .3, .62, 1],
        ),
      ),
      child: Stack(
        children: [
          Positioned.fill(
            child: IgnorePointer(
              child: DecoratedBox(
                decoration: BoxDecoration(
                  gradient: RadialGradient(
                    center: Alignment(-.08 + .16 * b, -.35 + .1 * b),
                    radius: .55 + .1 * b,
                    colors: [
                      const Color(0xFFA0D7FF).withValues(alpha: .3 + .25 * b),
                      const Color(0x00A0D7FF),
                    ],
                  ),
                ),
              ),
            ),
          ),
          child,
        ],
      ),
    );
  }
}

/// Le reflet qui passe sur « Commencer » : [sweep] va de 0 à 1.
class ShineSweep extends StatelessWidget {
  const ShineSweep({super.key, required this.sweep, required this.child});

  final double sweep;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(16),
      child: Stack(
        children: [
          child,
          if (sweep > 0 && sweep < 1)
            Positioned.fill(
              child: IgnorePointer(
                child: LayoutBuilder(
                  builder: (context, box) {
                    final w = box.maxWidth * .4;
                    final x = -w * 1.5 + (box.maxWidth + w * 2.5) * sweep;
                    return Stack(
                      children: [
                        Positioned(
                          left: x,
                          top: 0,
                          bottom: 0,
                          width: w,
                          child: Transform(
                            transform: Matrix4.skewX(-.3),
                            child: const DecoratedBox(
                              decoration: BoxDecoration(
                                gradient: LinearGradient(
                                  colors: [
                                    Color(0x00FFFFFF),
                                    Color(0x470A8CFF),
                                    Color(0x00FFFFFF),
                                  ],
                                ),
                              ),
                            ),
                          ),
                        ),
                      ],
                    );
                  },
                ),
              ),
            ),
        ],
      ),
    );
  }
}

/// Reflet toutes les quelques secondes, après l'entrée.
class ShineTimer {
  ShineTimer(this.controller);

  final AnimationController controller;
  Timer? _timer;

  void start(Duration first, Duration every) {
    _timer = Timer(first, () {
      controller.forward(from: 0);
      _timer = Timer.periodic(every, (_) => controller.forward(from: 0));
    });
  }

  void dispose() => _timer?.cancel();
}
