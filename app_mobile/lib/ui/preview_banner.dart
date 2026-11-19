import 'package:flutter/material.dart';

import '../l10n/app_localizations.dart';
import 'theme.dart';

/// Vrai pour l'aperçu publié (données fictives) :
/// flutter build web --dart-define=NEXIS_APERCU=true
const bool isPreview = bool.fromEnvironment('NEXIS_APERCU');

/// Bandeau discret en haut de l'écran, seulement dans l'aperçu.
class PreviewBanner extends StatelessWidget {
  const PreviewBanner({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    if (!isPreview) return child;
    final top = MediaQuery.paddingOf(context).top;
    return Stack(
      children: [
        child,
        Positioned(
          top: top + 4,
          left: 0,
          right: 0,
          child: IgnorePointer(
            child: Center(
              child: DecoratedBox(
                decoration: BoxDecoration(
                  color: NexisColors.navy.withValues(alpha: .82),
                  borderRadius: BorderRadius.circular(99),
                ),
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 3,
                  ),
                  child: Text(
                    AppLocalizations.of(context).previewBanner,
                    // Au-dessus du Navigator : pas de style de texte hérité.
                    style: body(
                      10.5,
                      weight: FontWeight.w600,
                      color: Colors.white,
                    ).copyWith(decoration: TextDecoration.none),
                    textDirection: TextDirection.ltr,
                  ),
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}
