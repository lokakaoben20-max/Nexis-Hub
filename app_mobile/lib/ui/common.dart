import 'package:flutter/material.dart';

import 'icons.dart';

import '../data/models.dart';
import '../l10n/app_localizations.dart';
import 'theme.dart';

/// Icône (série finale Nexis, comme les maquettes) et couleur de chaque service.
({IconData icon, Color color}) serviceVisual(Service service) =>
    switch (service) {
      Service.plomberie => (
        icon: NxService.plomberie,
        color: const Color(0xFF0350E6),
      ),
      Service.electricite => (
        icon: NxService.electricite,
        color: const Color(0xFFC98200),
      ),
      Service.climatisation => (
        icon: NxService.climatisation,
        color: const Color(0xFF0A84D6),
      ),
      Service.informatique => (
        icon: NxService.informatique,
        color: const Color(0xFF021937),
      ),
      Service.graphisme => (
        icon: NxService.graphisme,
        color: const Color(0xFF494C95),
      ),
      Service.coiffure => (
        icon: NxService.coiffure,
        color: const Color(0xFFC2416B),
      ),
      Service.nettoyage => (
        icon: NxService.nettoyage,
        color: const Color(0xFF1E8A4C),
      ),
      Service.jardinage => (
        icon: NxService.jardinage,
        color: const Color(0xFF4F8A10),
      ),
      Service.autre => (icon: NxService.autre, color: const Color(0xFF5B667A)),
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

String catalogServiceName(CatalogService item, String lang) {
  final translation = item.translations[lang];
  if (translation != null && translation.trim().isNotEmpty) return translation;
  final service = item.service;
  return service == null ? item.name : serviceName(service, lang);
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

/// Couleurs des pastilles des maquettes (fond, texte), claires et sombres.
enum PillTone { secured, ok, info, warn, wait, bad }

(Color, Color) _pillColors(PillTone tone, bool dark) => switch (tone) {
  PillTone.secured =>
    dark
        ? (const Color(0xFF1A2B4D), const Color(0xFF8DB4FF))
        : (const Color(0xFFE8F0FE), const Color(0xFF0A3D9E)),
  PillTone.ok =>
    dark
        ? (const Color(0xFF12301F), const Color(0xFF5BD08A))
        : (const Color(0xFFE3F5EA), const Color(0xFF17663A)),
  PillTone.info =>
    dark
        ? (const Color(0xFF22234A), const Color(0xFFB3B5F2))
        : (const Color(0xFFECECF8), const Color(0xFF3B3E80)),
  PillTone.warn =>
    dark
        ? (const Color(0xFF33270D), const Color(0xFFF2C661))
        : (const Color(0xFFFFF1D6), const Color(0xFF7A4E00)),
  PillTone.wait =>
    dark
        ? (const Color(0xFF1A2740), const Color(0xFFA9B4C6))
        : (const Color(0xFFEEF1F5), const Color(0xFF4E5B70)),
  PillTone.bad =>
    dark
        ? (const Color(0xFF3A1715), const Color(0xFFFF8A80))
        : (const Color(0xFFFDECEA), const Color(0xFFB42318)),
};

/// Pastille de la maquette : icône facultative et texte.
/// [compact] : la petite pastille sans icône de la liste des mouvements.
class Pill extends StatelessWidget {
  const Pill({
    super.key,
    required this.tone,
    required this.text,
    this.icon,
    this.compact = false,
  });

  final PillTone tone;
  final String text;
  final IconData? icon;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final (bg, fg) = _pillColors(tone, dark);
    return Container(
      padding: compact
          ? const EdgeInsets.symmetric(horizontal: 7, vertical: 2)
          : const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(99),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null && !compact) ...[
            Icon(icon, size: 13, color: fg),
            const SizedBox(width: 5),
          ],
          Flexible(
            child: Text(
              text,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: body(
                compact ? 10.5 : 11.5,
                weight: FontWeight.w600,
                color: fg,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Les états de l'argent : un mot, une icône, une couleur (charte).
class PaymentPill extends StatelessWidget {
  const PaymentPill(this.state, {super.key, this.text, this.compact = false});

  final PaymentState state;
  final String? text;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final (IconData icon, PillTone tone, String label) = switch (state) {
      PaymentState.secured => (
        PhFill.shieldCheck,
        PillTone.secured,
        l.paySecured,
      ),
      PaymentState.released => (PhFill.checkCircle, PillTone.ok, l.payReleased),
      PaymentState.refunded => (
        PhFill.arrowCounterClockwise,
        PillTone.info,
        l.payRefunded,
      ),
      PaymentState.blocked => (PhFill.lock, PillTone.bad, l.payBlocked),
      PaymentState.available => (PhFill.wallet, PillTone.ok, l.payAvailable),
      PaymentState.none => (PhRegular.clock, PillTone.wait, ''),
    };
    return Pill(tone: tone, text: text ?? label, icon: icon, compact: compact);
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

/// Bouton retour rond et blanc des maquettes (n-back).
class RoundBack extends StatelessWidget {
  const RoundBack({super.key});

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Semantics(
      button: true,
      label: MaterialLocalizations.of(context).backButtonTooltip,
      excludeSemantics: true,
      child: GestureDetector(
        onTap: () => Navigator.maybePop(context),
        child: Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: p.surface,
            shape: BoxShape.circle,
            border: Border.all(color: dark ? p.line : const Color(0xFFE6E9EF)),
          ),
          child: Icon(PhRegular.caretLeft, size: 18, color: p.ink),
        ),
      ),
    );
  }
}

/// Barre du haut des écrans d'entrée : seulement le bouton retour rond.
PreferredSizeWidget roundBackBar(BuildContext context) => AppBar(
  backgroundColor: context.palette.bg,
  surfaceTintColor: Colors.transparent,
  automaticallyImplyLeading: false,
  leadingWidth: 58,
  leading: const Padding(
    padding: EdgeInsets.only(left: 18),
    child: Center(child: RoundBack()),
  ),
);
