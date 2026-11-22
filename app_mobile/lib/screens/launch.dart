import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../ui/theme.dart';
import 'welcome_intro.dart' show AssemblingMonogram, introStep;

/// Écran de lancement (maquette design/app-ouverture-lancement.html, choix
/// de Ben le 2026-11-22) : le monogramme blanc seul au centre sur le bleu
/// Nexis, avec une lueur qui respire, et le nom « Nexis Hub » en petit en
/// bas qui apparaît en fondu. Ni slogan, ni barre de chargement.
///
/// Dure un peu moins de deux secondes, puis [onDone]. Quand le téléphone
/// demande moins d'animations, l'écran reste fixe, sans lueur qui respire.
class LaunchScreen extends StatefulWidget {
  const LaunchScreen({super.key, required this.onDone});

  final VoidCallback onDone;

  @override
  State<LaunchScreen> createState() => _LaunchScreenState();
}

class _LaunchScreenState extends State<LaunchScreen>
    with TickerProviderStateMixin {
  static const _total = Duration(milliseconds: 1900);
  late final AnimationController _run = AnimationController(
    vsync: this,
    duration: _total,
  );
  late final AnimationController _breath = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 2600),
  );
  bool _started = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_started) return;
    _started = true;
    if (!MediaQuery.disableAnimationsOf(context)) _breath.repeat(reverse: true);
    _run.forward().whenComplete(() {
      if (mounted) widget.onDone();
    });
  }

  @override
  void dispose() {
    _run.dispose();
    _breath.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final reduce = MediaQuery.disableAnimationsOf(context);
    final bottom = MediaQuery.paddingOf(context).bottom;
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light,
      child: Scaffold(
        backgroundColor: NexisColors.brand,
        body: AnimatedBuilder(
          animation: Listenable.merge([_run, _breath]),
          builder: (context, _) {
            final seconds = _run.value * _total.inMilliseconds / 1000;
            // Le monogramme entre en .9 s en grossissant de .88 à 1 ;
            // le nom arrive après .5 s, en 1,2 s.
            final logo = reduce ? 1.0 : introStep(seconds, 0, .9);
            final name = reduce ? 1.0 : introStep(seconds, .5, 1.7);
            final b = reduce ? 0.0 : Curves.easeInOut.transform(_breath.value);
            return DecoratedBox(
              decoration: const BoxDecoration(
                gradient: RadialGradient(
                  center: Alignment(0, -.1),
                  radius: 1.0,
                  colors: [
                    Color(0xFF1A8CFF),
                    NexisColors.brand,
                    Color(0xFF0237A8),
                  ],
                  stops: [0, .55, 1],
                ),
              ),
              child: Stack(
                alignment: Alignment.center,
                children: [
                  Transform.scale(
                    scale: 1 + .12 * b,
                    child: Opacity(
                      opacity: 1 - .3 * b,
                      child: const SizedBox(
                        width: 300,
                        height: 300,
                        child: DecoratedBox(
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            gradient: RadialGradient(
                              colors: [Color(0x44FFFFFF), Color(0x00FFFFFF)],
                              stops: [0, .7],
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                  Opacity(
                    opacity: logo,
                    child: Transform.scale(
                      scale: .88 + .12 * logo,
                      child: Semantics(
                        label: 'Nexis Hub',
                        image: true,
                        child: ExcludeSemantics(
                          // Les trois barres du logo, 73 px de large comme la
                          // maquette (monogramme de 150 px dans un carré de 2000).
                          child: const AssemblingMonogram(
                            seconds: 99,
                            width: 73,
                          ),
                        ),
                      ),
                    ),
                  ),
                  Positioned(
                    bottom: 64 + bottom,
                    child: Opacity(
                      opacity: .95 * name,
                      child: Transform.scale(
                        scale: .88 + .12 * name,
                        child: ExcludeSemantics(
                          child: Image.asset(
                            'assets/images/logo-blanc.png',
                            width: 112,
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}
