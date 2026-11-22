import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../data/models.dart';
import '../l10n/app_localizations.dart';
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

/// Les trois cartes « Prestataire vérifié » empilées (proposition C
/// retenue par Ben le 2026-11-22, design/app-connexion-frontend-design.html) :
/// elles tombent l'une après l'autre et rebondissent deux fois.
class VerifiedFan extends StatelessWidget {
  const VerifiedFan({super.key, required this.elapsed});

  /// Secondes écoulées depuis le début de l'écran ; 99 = état final.
  final double elapsed;

  static const fallSeconds = 2.8;
  static const totalSeconds = 1.45 + fallSeconds;

  // (service, haut, rotation en degrés, échelle, fond, délai) : dans
  // l'ordre de peinture de la maquette, la carte du haut est dessinée
  // en dernier.
  static const _cards = [
    (Service.plomberie, 128.0, -1.5, 1.0, Color(0xFFFFFFFF), .85),
    (Service.electricite, 64.0, 3.0, .97, Color(0xFFF2F7FF), 1.15),
    (Service.nettoyage, 0.0, -5.0, .94, Color(0xFFE3EEFF), 1.45),
  ];

  /// Hauteur (en px) et opacité de la chute : mêmes jalons que les
  /// images clés `fall` de la maquette.
  static (double, double) pose(double t) {
    t = t.clamp(0.0, 1.0);
    const fall = Cubic(.55, 0, 1, .45);
    const settle = Cubic(.2, .6, .4, 1);
    double seg(double a, double b, double from, double to, Curve c) =>
        from + (to - from) * c.transform((t - a) / (b - a));
    final y = t < .52
        ? seg(0, .52, -820, 0, fall)
        : t < .68
        ? seg(.52, .68, 0, -22, settle)
        : t < .80
        ? seg(.68, .80, -22, 0, fall)
        : t < .89
        ? seg(.80, .89, 0, -7, settle)
        : t < .96
        ? seg(.89, .96, -7, 0, fall)
        : 0.0;
    return (y, (t / .06).clamp(0.0, 1.0));
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final lang = langOf(context);
    return ExcludeSemantics(
      child: SizedBox(
        width: 280,
        height: 216,
        child: Stack(
          clipBehavior: Clip.none,
          children: [
            for (final (service, top, rotation, scale, fill, delay) in _cards)
              Builder(
                builder: (context) {
                  final (dy, opacity) = pose((elapsed - delay) / fallSeconds);
                  final visual = serviceVisual(service);
                  return Positioned(
                    top: top,
                    left: 0,
                    right: 0,
                    child: Opacity(
                      opacity: opacity,
                      child: Transform.translate(
                        offset: Offset(0, dy),
                        child: Transform.rotate(
                          angle: rotation * math.pi / 180,
                          child: Transform.scale(
                            scale: scale,
                            child: Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 14,
                                vertical: 12,
                              ),
                              decoration: BoxDecoration(
                                color: fill,
                                borderRadius: BorderRadius.circular(20),
                                boxShadow: const [
                                  BoxShadow(
                                    color: Color(0x8C021937),
                                    offset: Offset(0, 18),
                                    blurRadius: 30,
                                    spreadRadius: -16,
                                  ),
                                ],
                              ),
                              child: Row(
                                children: [
                                  Container(
                                    width: 44,
                                    height: 44,
                                    decoration: BoxDecoration(
                                      color: visual.color,
                                      borderRadius: BorderRadius.circular(13),
                                      boxShadow: [
                                        BoxShadow(
                                          color: Colors.white.withValues(
                                            alpha: .9,
                                          ),
                                          spreadRadius: 2,
                                        ),
                                      ],
                                    ),
                                    child: Icon(
                                      visual.icon,
                                      size: 24,
                                      color: Colors.white,
                                    ),
                                  ),
                                  const SizedBox(width: 12),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          serviceName(service, lang),
                                          style: title(
                                            15,
                                            color: NexisColors.navy,
                                          ),
                                        ),
                                        Text(
                                          l.verifiedProvider,
                                          style: body(
                                            12.5,
                                            color: const Color(0xFF4E5B70),
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                  const Icon(
                                    PhFill.sealCheck,
                                    size: 24,
                                    color: NexisColors.brand,
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),
                  );
                },
              ),
          ],
        ),
      ),
    );
  }
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
