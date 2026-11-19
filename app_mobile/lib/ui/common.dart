import 'package:flutter/material.dart';

import 'icons.dart';

import '../data/models.dart';
import '../l10n/app_localizations.dart';
import 'theme.dart';

/// Icône et couleur de chaque service (mêmes couleurs que la Mini App).
({IconData icon, Color color}) serviceVisual(
  Service service,
) => switch (service) {
  Service.plomberie => (icon: PhFill.wrench, color: const Color(0xFF0350E6)),
  Service.electricite => (
    icon: PhFill.lightning,
    color: const Color(0xFFC98200),
  ),
  Service.climatisation => (
    icon: PhFill.snowflake,
    color: const Color(0xFF0A84D6),
  ),
  Service.informatique => (
    icon: PhFill.desktop,
    color: const Color(0xFF021937),
  ),
  Service.graphisme => (icon: PhFill.palette, color: const Color(0xFF494C95)),
  Service.coiffure => (icon: PhFill.scissors, color: const Color(0xFFC2416B)),
  Service.nettoyage => (icon: PhFill.broom, color: const Color(0xFF1E8A4C)),
  Service.jardinage => (icon: PhFill.plant, color: const Color(0xFF4F8A10)),
  Service.autre => (icon: PhFill.plusCircle, color: const Color(0xFF5B667A)),
};

/// Noms des services : les mêmes que dans le bot (FR / LN / EN).
String serviceName(Service service, String lang) {
  const names = {
    Service.plomberie: ['Plomberie', 'Plomberie', 'Plumbing'],
    Service.electricite: ['Électricité', 'Kokotisa mwinda', 'Electrical'],
    Service.climatisation: [
      'Climatisation',
      'Climatisation',
      'Air conditioning',
    ],
    Service.informatique: ['Informatique', 'Informatique', 'IT'],
    Service.graphisme: ['Graphisme', 'Graphisme', 'Graphic design'],
    Service.coiffure: ['Coiffure', 'Kosala nsuki', 'Hairdressing'],
    Service.nettoyage: ['Nettoyage', 'Kopetola', 'Cleaning'],
    Service.jardinage: ['Jardinage', 'Jardin', 'Gardening'],
    Service.autre: ['Autre service', 'Mosala mosusu', 'Other service'],
  };
  final index = const ['fr', 'ln', 'en'].indexOf(lang);
  return names[service]![index < 0 ? 0 : index];
}

class ServiceBadge extends StatelessWidget {
  const ServiceBadge(this.service, {super.key, this.size = 44});

  final Service service;
  final double size;

  @override
  Widget build(BuildContext context) {
    final visual = serviceVisual(service);
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: context.palette.surface,
        shape: BoxShape.circle,
        border: Border.all(color: context.palette.line),
      ),
      alignment: Alignment.center,
      child: Icon(visual.icon, size: size * .5, color: visual.color),
    );
  }
}

/// Les états de l'argent : un mot, une icône, une couleur (charte).
class PaymentPill extends StatelessWidget {
  const PaymentPill(this.state, {super.key, this.text});

  final PaymentState state;
  final String? text;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final (IconData icon, Color color, String label) = switch (state) {
      PaymentState.secured => (
        PhFill.shieldCheck,
        NexisColors.brand,
        l.paySecured,
      ),
      PaymentState.released => (
        PhFill.checkCircle,
        NexisColors.ok,
        l.payReleased,
      ),
      PaymentState.refunded => (
        PhFill.arrowCounterClockwise,
        NexisColors.violet,
        l.payRefunded,
      ),
      PaymentState.blocked => (PhFill.lock, NexisColors.danger, l.payBlocked),
      PaymentState.available => (PhFill.wallet, NexisColors.ok, l.payAvailable),
      PaymentState.none => (PhRegular.clock, context.palette.muted, ''),
    };
    final dark = Theme.of(context).brightness == Brightness.dark;
    final shown = dark && color == NexisColors.brand
        ? context.palette.softInk
        : color;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: shown.withValues(alpha: dark ? .18 : .1),
        borderRadius: BorderRadius.circular(99),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: shown),
          const SizedBox(width: 4),
          Flexible(
            child: Text(
              text ?? label,
              overflow: TextOverflow.ellipsis,
              style: body(11.5, weight: FontWeight.w600, color: shown),
            ),
          ),
        ],
      ),
    );
  }
}

/// Bouton principal : dégradé de la charte, texte Unbounded.
class PrimaryButton extends StatelessWidget {
  const PrimaryButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final enabled = onPressed != null;
    return Semantics(
      button: true,
      enabled: enabled,
      child: Opacity(
        opacity: enabled ? 1 : .45,
        child: DecoratedBox(
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [NexisColors.gradientStart, NexisColors.gradientEnd],
            ),
            borderRadius: BorderRadius.circular(16),
          ),
          child: Material(
            color: Colors.transparent,
            child: InkWell(
              borderRadius: BorderRadius.circular(16),
              onTap: onPressed,
              child: SizedBox(
                height: 54,
                width: double.infinity,
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    if (icon != null) ...[
                      Icon(icon, color: Colors.white, size: 20),
                      const SizedBox(width: 8),
                    ],
                    Text(label, style: title(15, color: Colors.white)),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Fenêtre « bientôt » pour ce que l'aperçu ne fait pas encore.
void showComingSoon(BuildContext context, String what) {
  final l = AppLocalizations.of(context);
  showModalBottomSheet<void>(
    context: context,
    backgroundColor: context.palette.surface,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
    ),
    builder: (context) => SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 24, 20, 16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(what, style: title(18, color: context.palette.ink)),
            const SizedBox(height: 6),
            Text(
              l.comingSoonText,
              style: body(14, color: context.palette.muted),
            ),
            const SizedBox(height: 20),
            PrimaryButton(label: l.ok, onPressed: () => Navigator.pop(context)),
          ],
        ),
      ),
    ),
  );
}

String langOf(BuildContext context) =>
    Localizations.localeOf(context).languageCode;
