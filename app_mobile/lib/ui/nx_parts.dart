import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../data/models.dart';
import '../data/money.dart';
import '../l10n/app_localizations.dart';
import 'common.dart';
import 'nx_icon.dart';
import 'theme.dart';

/// Pièces communes des écrans client refaits d'après la maquette validée
/// (design/app-accueil-frontend-design.html) : fond uni, cartes blanches
/// à fin liseré, pastilles de service pleines, états en clair.

bool isDark(BuildContext context) =>
    Theme.of(context).brightness == Brightness.dark;

/// Fond de page (#F3F5F9 dans la maquette).
Color pageColor(BuildContext context) =>
    isDark(context) ? context.palette.bg : const Color(0xFFF3F5F9);

Color mutedColor(BuildContext context) =>
    isDark(context) ? context.palette.muted : const Color(0xFF4E5B70);

Color faintColor(BuildContext context) =>
    isDark(context) ? context.palette.muted : const Color(0xFF8A95A8);

/// Carte blanche : rayon 20 et liseré rgba(2,25,55,.07).
BoxDecoration nxCard(BuildContext context, {double radius = 20}) =>
    BoxDecoration(
      color: context.palette.surface,
      borderRadius: BorderRadius.circular(radius),
      border: Border.all(
        color: isDark(context) ? context.palette.line : const Color(0x12021937),
      ),
    );

/// Pastille de service : pictogramme blanc plein sur carré arrondi de la
/// couleur du service (série B). [glyph] sert aux services que l'app ne
/// connaît pas encore (publiés par le serveur).
class ServiceTile extends StatelessWidget {
  const ServiceTile({
    super.key,
    required this.color,
    this.icon,
    this.glyph,
    this.size = 46,
    this.badge,
  }) : assert(icon != null || glyph != null);

  final Color color;
  final IconData? icon;
  final String? glyph;
  final double size;

  /// Mention posée au coin (« Nouveau »).
  final Widget? badge;

  @override
  Widget build(BuildContext context) {
    final inner = size * .565;
    final tile = Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(size * .32),
        boxShadow: [
          BoxShadow(
            color: color.withValues(alpha: .5),
            offset: Offset(0, size * .17),
            blurRadius: size * .3,
            spreadRadius: -size * .17,
          ),
        ],
      ),
      alignment: Alignment.center,
      child: icon != null
          ? ExcludeSemantics(
              child: Icon(icon, size: inner, color: Colors.white),
            )
          : NxIcon(glyph!, size: inner, color: Colors.white),
    );
    if (badge == null) return tile;
    return Stack(
      clipBehavior: Clip.none,
      children: [
        tile,
        Positioned(right: -14, top: -8, child: badge!),
      ],
    );
  }
}

/// La pastille d'un service connu de l'app.
class KnownServiceTile extends StatelessWidget {
  const KnownServiceTile(this.service, {super.key, this.size = 46});

  final Service service;
  final double size;

  @override
  Widget build(BuildContext context) {
    final visual = serviceVisual(service);
    return ServiceTile(color: visual.color, icon: visual.icon, size: size);
  }
}

/// « Nouveau » : petite pastille rouge de la maquette.
class NewBadge extends StatelessWidget {
  const NewBadge({super.key, this.ringColor});

  final Color? ringColor;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: const Color(0xFFE5484D),
        borderRadius: BorderRadius.circular(99),
        boxShadow: ringColor == null
            ? null
            : [BoxShadow(color: ringColor!, spreadRadius: 2)],
      ),
      child: Text(
        l.newBadge,
        style: body(
          10,
          weight: FontWeight.w700,
          color: Colors.white,
          height: 1.2,
        ),
      ),
    );
  }
}

/// Ton d'une pastille d'état.
enum StatusKind { live, warn, done, secured, bad, wait }

/// Pastille d'état : texte en clair, icône facultative, point qui pulse
/// pour une mission en route (une seule fois, sauf si l'animation est
/// réduite).
class StatusChip extends StatefulWidget {
  const StatusChip({
    super.key,
    required this.kind,
    required this.text,
    this.icon,
    this.pulse = false,
    this.compact = false,
  });

  final StatusKind kind;
  final String text;
  final String? icon;
  final bool pulse;
  final bool compact;

  @override
  State<StatusChip> createState() => _StatusChipState();
}

class _StatusChipState extends State<StatusChip>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1800),
  );
  bool _started = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_started || !widget.pulse) return;
    _started = true;
    if (!MediaQuery.disableAnimationsOf(context)) {
      // Trois pulsations, comme la maquette.
      _c.repeat();
      Future<void>.delayed(const Duration(milliseconds: 5400), () {
        if (mounted) _c.stop();
      });
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  (Color, Color) _colors(bool dark) => switch (widget.kind) {
    StatusKind.live =>
      dark
          ? (const Color(0xFF1A2B4D), const Color(0xFF8DB4FF))
          : (const Color(0xFFE8F0FE), const Color(0xFF0A3D9E)),
    StatusKind.warn =>
      dark
          ? (const Color(0xFF33270D), const Color(0xFFF2C661))
          : (const Color(0xFFFDF1D8), const Color(0xFF8A5A00)),
    StatusKind.done =>
      dark
          ? (const Color(0xFF12301F), const Color(0xFF5BD08A))
          : (const Color(0xFFE6F4EA), const Color(0xFF1E7A3C)),
    StatusKind.secured =>
      dark
          ? (const Color(0xFF22234A), const Color(0xFFB3B5F2))
          : (const Color(0xFFEEEEF8), const Color(0xFF494C95)),
    StatusKind.bad =>
      dark
          ? (const Color(0xFF3A1A1A), const Color(0xFFFF9C94))
          : (const Color(0xFFFDECEA), const Color(0xFFB42318)),
    StatusKind.wait =>
      dark
          ? (const Color(0xFF1A2740), const Color(0xFFA9B4C6))
          : (const Color(0xFFEEF1F5), const Color(0xFF4E5B70)),
  };

  @override
  Widget build(BuildContext context) {
    final (bg, fg) = _colors(isDark(context));
    final small = widget.compact;
    return Container(
      height: small ? 22 : 24,
      padding: EdgeInsets.symmetric(horizontal: small ? 8 : 10),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(99),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (widget.pulse) ...[
            AnimatedBuilder(
              animation: _c,
              builder: (context, _) => Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: NexisColors.brand,
                  boxShadow: [
                    BoxShadow(
                      color: NexisColors.brand.withValues(
                        alpha: .5 * (1 - _c.value),
                      ),
                      spreadRadius: 8 * _c.value,
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(width: 6),
          ] else if (widget.icon != null) ...[
            NxIcon(widget.icon!, size: 14, color: fg),
            const SizedBox(width: 6),
          ],
          Flexible(
            child: Text(
              widget.text,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: body(
                small ? 11.5 : 12.5,
                weight: FontWeight.w600,
                color: fg,
                height: 1.2,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Onglets soulignés « En cours · 3 / Terminées » de la maquette.
class UnderlineTabs extends StatelessWidget {
  const UnderlineTabs({
    super.key,
    required this.labels,
    required this.selected,
    required this.onChanged,
    this.badges = const {},
  });

  final List<String> labels;
  final int selected;
  final ValueChanged<int> onChanged;

  /// Pastille de nombre sur un onglet (index → nombre).
  final Map<int, int> badges;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Container(
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: p.line)),
      ),
      child: Row(
        children: [
          for (var i = 0; i < labels.length; i++) ...[
            if (i > 0) const SizedBox(width: 22),
            Semantics(
              button: true,
              selected: i == selected,
              child: GestureDetector(
                behavior: HitTestBehavior.opaque,
                onTap: () => onChanged(i),
                child: Container(
                  padding: const EdgeInsets.only(top: 6, bottom: 11),
                  decoration: BoxDecoration(
                    border: Border(
                      bottom: BorderSide(
                        color: i == selected
                            ? (isDark(context)
                                  ? const Color(0xFF5B8CFF)
                                  : NexisColors.brand)
                            : Colors.transparent,
                        width: 3,
                      ),
                    ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        labels[i],
                        style: body(
                          15,
                          weight: FontWeight.w600,
                          color: i == selected ? p.ink : faintColor(context),
                        ),
                      ),
                      if (badges[i] != null && badges[i]! > 0) ...[
                        const SizedBox(width: 7),
                        Container(
                          constraints: const BoxConstraints(minWidth: 20),
                          height: 20,
                          padding: const EdgeInsets.symmetric(horizontal: 6),
                          alignment: Alignment.center,
                          decoration: BoxDecoration(
                            color: NexisColors.brand,
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Text(
                            '${badges[i]}',
                            style: body(
                              12,
                              weight: FontWeight.w600,
                              color: Colors.white,
                              height: 1.1,
                            ),
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// Bouton carré blanc de l'en-tête (retour, cloche).
class SquareButton extends StatelessWidget {
  const SquareButton({
    super.key,
    required this.child,
    required this.label,
    required this.onTap,
  });

  final Widget child;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: label,
      excludeSemantics: true,
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          width: 42,
          height: 42,
          decoration: nxCard(context, radius: 14),
          alignment: Alignment.center,
          child: child,
        ),
      ),
    );
  }
}

/// Note du prestataire : « ★ 4,8  126 avis », tels que le serveur les donne.
String ratingText(double rating, String lang) {
  final text = rating.toStringAsFixed(1);
  return lang == 'en' ? text : text.replaceAll('.', ',');
}

/// Montant d'une mission pour l'étiquette de droite d'une carte.
String? missionAmountText(Mission m, AppLocalizations l, String lang) {
  if (m.amount != null) return formatMoney(m.amount!, lang);
  if (m.status == MissionStatus.quoted) return l.quotesPill(m.quotesCount);
  return null;
}

/// Le texte « 12 nov. » d'une date, dans la langue de l'app.
String shortDate(BuildContext context, DateTime date) =>
    MaterialLocalizations.of(context).formatShortMonthDay(date);

/// Icône de la ligne d'un groupe de réglages (carré clair, icône bleue ;
/// violet pour l'aide et les litiges).
class SoftIconBox extends StatelessWidget {
  const SoftIconBox({
    super.key,
    required this.glyph,
    this.violet = false,
    this.size = 40,
  });

  final String glyph;
  final bool violet;
  final double size;

  @override
  Widget build(BuildContext context) {
    final dark = isDark(context);
    final p = context.palette;
    final bg = violet
        ? (dark ? const Color(0xFF22234A) : const Color(0xFFEEEEF8))
        : p.soft;
    final fg = violet
        ? (dark ? const Color(0xFFB3B5F2) : const Color(0xFF494C95))
        : (dark ? p.softInk : NexisColors.brand);
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(13),
      ),
      alignment: Alignment.center,
      child: NxIcon(glyph, size: 22, color: fg),
    );
  }
}

/// Icône de service d'un [CatalogService].
Widget catalogTile(CatalogService s, {double size = 46, Widget? badge}) {
  if (s.service != null) {
    final visual = serviceVisual(s.service!);
    return ServiceTile(
      color: Color(s.color),
      icon: visual.icon,
      size: size,
      badge: badge,
    );
  }
  return ServiceTile(
    color: Color(s.color),
    glyph: s.glyph ?? 'svcPeinture',
    size: size,
    badge: badge,
  );
}

/// Date en toutes lettres (« 20 novembre »). Le lingala emprunte les noms
/// de mois au français, comme le reste des textes système.
String longDate(BuildContext context, DateTime date) {
  final lang = langOf(context);
  return DateFormat.MMMMd(lang == 'ln' ? 'fr' : lang).format(date);
}

/// Le mois seul (« novembre »).
String monthName(BuildContext context, DateTime date) {
  final lang = langOf(context);
  return DateFormat.MMMM(lang == 'ln' ? 'fr' : lang).format(date);
}
