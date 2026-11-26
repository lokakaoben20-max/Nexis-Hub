import 'package:flutter/material.dart';

/// Couleurs de la charte Nexis (design/cadrage-design-2026-11-06.md).
class NexisColors {
  static const brand = Color(0xFF0A63F0);
  static const navy = Color(0xFF021937);
  static const gradientStart = Color(
    0xFF0870EE,
  ); // dégradé E, version sûre pour le texte
  static const gradientEnd = Color(0xFF0350E6);
  static const halo = Color(0xFF0A8CFF);
  static const skyTop = Color(0xFF9FD3FF);
  static const skyBottom = Color(0xFFF4F9FF);
  static const violet = Color(0xFF494C95);
  static const ok = Color(0xFF1E8A4C);
  static const danger = Color(0xFFC62828);
  static const wait = Color(0xFFB26A00);
}

@immutable
class NexisPalette extends ThemeExtension<NexisPalette> {
  const NexisPalette({
    required this.bg,
    required this.surface,
    required this.ink,
    required this.muted,
    required this.line,
    required this.soft,
    required this.softInk,
  });

  final Color bg, surface, ink, muted, line, soft, softInk;

  static const light = NexisPalette(
    bg: Color(0xFFF6F8FB),
    surface: Colors.white,
    ink: NexisColors.navy,
    muted: Color(0xFF5B667A),
    line: Color(0xFFE3E8F0),
    soft: Color(0xFFE8F0FE),
    softInk: NexisColors.brand,
  );
  static const dark = NexisPalette(
    bg: Color(0xFF0B1424),
    surface: Color(0xFF121E33),
    ink: Color(0xFFEAF0FA),
    muted: Color(0xFF9AA7BD),
    line: Color(0xFF22314B),
    soft: Color(0xFF1A2B4D),
    softInk: Color(0xFF8DB4FF),
  );

  @override
  NexisPalette copyWith() => this;

  @override
  NexisPalette lerp(NexisPalette? other, double t) =>
      t < .5 ? this : (other ?? this);
}

extension NexisContext on BuildContext {
  NexisPalette get palette => Theme.of(this).extension<NexisPalette>()!;
}

/// Les deux polices sont variables : le poids passe par fontVariations.
TextStyle title(
  double size, {
  FontWeight weight = FontWeight.w600,
  Color? color,
  double? height,
}) => TextStyle(
  fontFamily: 'Unbounded',
  fontSize: size,
  fontWeight: weight,
  color: color,
  height: height ?? 1.2,
  fontVariations: [FontVariation.weight(weight.value.toDouble())],
);

TextStyle body(
  double size, {
  FontWeight weight = FontWeight.w400,
  Color? color,
  double? height,
}) => TextStyle(
  fontFamily: 'Inter',
  fontSize: size,
  fontWeight: weight,
  color: color,
  height: height ?? 1.4,
  fontVariations: [FontVariation.weight(weight.value.toDouble())],
);

ThemeData nexisTheme(Brightness brightness) {
  final palette = brightness == Brightness.dark
      ? NexisPalette.dark
      : NexisPalette.light;
  final base = ThemeData(
    brightness: brightness,
    useMaterial3: true,
    colorScheme: ColorScheme.fromSeed(
      seedColor: NexisColors.brand,
      brightness: brightness,
      primary: brightness == Brightness.dark
          ? const Color(0xFF5B8CFF)
          : NexisColors.brand,
      surface: palette.surface,
    ),
    scaffoldBackgroundColor: palette.bg,
    fontFamily: 'Inter',
    extensions: [palette],
    splashFactory: InkSparkle.splashFactory,
  );
  return base.copyWith(
    textTheme: base.textTheme.apply(
      fontFamily: 'Inter',
      bodyColor: palette.ink,
      displayColor: palette.ink,
    ),
    dividerColor: palette.line,
  );
}
