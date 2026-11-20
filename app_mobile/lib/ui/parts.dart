import 'package:flutter/material.dart';

import 'icons.dart';
import 'theme.dart';
import 'common.dart';

/// Pièces communes des écrans du parcours (maquettes app-ecrans-v2/v3) :
/// barre du haut, carte, note bleue, avatar, note étoilée, boutons.

bool _dark(BuildContext context) =>
    Theme.of(context).brightness == Brightness.dark;

/// Haut d'écran : bouton retour rond, titre centré, sous-titre gris.
class NTopBar extends StatelessWidget {
  const NTopBar({super.key, required this.title, this.subtitle});

  final String title;
  final String? subtitle;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Row(
        children: [
          const RoundBack(),
          Expanded(
            child: Column(
              children: [
                Text(
                  title,
                  textAlign: TextAlign.center,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: _titleStyle(15, p.ink),
                ),
                if (subtitle != null)
                  Text(
                    subtitle!,
                    textAlign: TextAlign.center,
                    style: body(12, color: p.muted),
                  ),
              ],
            ),
          ),
          const SizedBox(width: 40),
        ],
      ),
    );
  }
}

TextStyle _titleStyle(double size, Color color) => title(size, color: color);

/// Carte blanche arrondie au liseré fin. [selected] : liseré bleu de 2.
class NCard extends StatelessWidget {
  const NCard({
    super.key,
    required this.child,
    this.selected = false,
    this.padding = const EdgeInsets.all(14),
  });

  final Widget child;
  final bool selected;
  final EdgeInsets padding;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: p.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: selected
              ? NexisColors.brand
              : (_dark(context) ? p.line : const Color(0xFFEEF1F5)),
          width: selected ? 2 : 1,
        ),
      ),
      child: child,
    );
  }
}

/// Note sur fond bleu clair, violet pour [violet] (aide, litige) ou
/// rose pour [danger] (argent bloqué).
class NInfo extends StatelessWidget {
  const NInfo({
    super.key,
    required this.text,
    this.icon = PhFill.shieldCheck,
    this.violet = false,
    this.danger = false,
  });

  final String text;
  final IconData icon;
  final bool violet;
  final bool danger;

  @override
  Widget build(BuildContext context) {
    final dark = _dark(context);
    final bg = danger
        ? (dark ? const Color(0xFF3A1715) : const Color(0xFFFFF6F5))
        : violet
        ? (dark ? const Color(0xFF22234A) : const Color(0xFFECECF8))
        : (dark ? const Color(0xFF1A2B4D) : const Color(0xFFE8F0FE));
    final fg = danger
        ? (dark ? const Color(0xFFFFB4AB) : const Color(0xFF7A3A33))
        : violet
        ? (dark ? const Color(0xFFB3B5F2) : const Color(0xFF3B3E80))
        : (dark ? const Color(0xFF8DB4FF) : const Color(0xFF0A3D9E));
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(top: 1),
            child: Icon(icon, size: 18, color: fg),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              text,
              style: body(12.5, color: fg).copyWith(height: 1.45),
            ),
          ),
        ],
      ),
    );
  }
}

/// Avatar rond aux initiales.
class NAvatar extends StatelessWidget {
  const NAvatar({
    super.key,
    required this.initials,
    required this.color,
    this.size = 42,
  });

  final String initials;
  final Color color;
  final double size;

  @override
  Widget build(BuildContext context) => Container(
    width: size,
    height: size,
    alignment: Alignment.center,
    decoration: BoxDecoration(color: color, shape: BoxShape.circle),
    child: Text(
      initials,
      style: body(size / 3, weight: FontWeight.w700, color: Colors.white),
    ),
  );
}

/// « ★ 4,9 (128) ».
class NStars extends StatelessWidget {
  const NStars({
    super.key,
    required this.rating,
    required this.reviews,
    required this.lang,
  });

  final double rating;
  final int reviews;
  final String lang;

  @override
  Widget build(BuildContext context) {
    final value = rating.toStringAsFixed(1);
    final shown = lang == 'en' ? value : value.replaceAll('.', ',');
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Icon(PhFill.star, size: 13, color: Color(0xFFE3A008)),
        const SizedBox(width: 3),
        Text(
          '$shown ($reviews)',
          style: body(12, weight: FontWeight.w600, color: context.palette.ink),
        ),
      ],
    );
  }
}

enum NButtonKind { primary, ghost, line }

/// Bouton des maquettes : dégradé E, bleu clair ou bordé ; petit ou grand.
class NButton extends StatelessWidget {
  const NButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.kind = NButtonKind.primary,
    this.small = false,
    this.icon,
    this.busy = false,
    this.danger = false,
  });

  final String label;
  final VoidCallback? onPressed;
  final NButtonKind kind;
  final bool small;
  final IconData? icon;
  final bool busy;

  /// Texte rouge sur fond blanc (« Ce n'est pas moi »).
  final bool danger;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final dark = _dark(context);
    final Color fg = switch (kind) {
      NButtonKind.primary => Colors.white,
      NButtonKind.ghost => p.softInk,
      NButtonKind.line => danger ? NexisColors.danger : p.ink,
    };
    final decoration = BoxDecoration(
      borderRadius: BorderRadius.circular(small ? 12 : 16),
      gradient: kind == NButtonKind.primary
          ? const LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [NexisColors.halo, NexisColors.gradientEnd],
            )
          : null,
      color: switch (kind) {
        NButtonKind.primary => null,
        NButtonKind.ghost => p.soft,
        NButtonKind.line => p.surface,
      },
      border: kind == NButtonKind.line
          ? Border.all(
              color: dark ? p.line : const Color(0xFFD5DBE5),
              width: 1.5,
            )
          : null,
    );
    final enabled = onPressed != null && !busy;
    return Semantics(
      button: true,
      enabled: enabled,
      child: Opacity(
        opacity: onPressed == null ? .45 : 1,
        child: GestureDetector(
          onTap: enabled ? onPressed : null,
          child: Container(
            height: small ? 38 : 50,
            padding: EdgeInsets.symmetric(horizontal: small ? 14 : 16),
            decoration: decoration,
            child: Row(
              mainAxisSize: small ? MainAxisSize.min : MainAxisSize.max,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                if (busy)
                  SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2, color: fg),
                  )
                else ...[
                  if (icon != null) ...[
                    Icon(icon, size: small ? 16 : 20, color: fg),
                    const SizedBox(width: 8),
                  ],
                  Flexible(
                    child: Text(
                      label,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: title(small ? 12.5 : 14.5, color: fg),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Fond et marges des écrans du parcours.
class NScreen extends StatelessWidget {
  const NScreen({super.key, required this.children, this.bottom});

  final List<Widget> children;

  /// Boutons collés en bas (« Payer 25 000 FC »).
  final Widget? bottom;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: context.palette.bg,
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(18, 8, 18, 18),
                children: [
                  for (var i = 0; i < children.length; i++) ...[
                    if (i > 0) const SizedBox(height: 14),
                    children[i],
                  ],
                ],
              ),
            ),
            if (bottom != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(18, 0, 18, 12),
                child: bottom,
              ),
          ],
        ),
      ),
    );
  }
}
