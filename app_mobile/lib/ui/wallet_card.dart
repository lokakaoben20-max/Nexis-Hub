import 'package:flutter/material.dart';

import 'icons.dart';

import '../data/models.dart';
import '../data/money.dart';
import '../l10n/app_localizations.dart';
import 'common.dart';
import 'theme.dart';

/// Carte portefeuille A (maquette app-accueil-reference) : la carte FC
/// devant, la carte USD qui dépasse derrière. Toucher la carte de derrière,
/// un point ou glisser change de portefeuille ; l'œil masque les montants.
///
/// Les mesures sont celles de la maquette (carte 228 × 136 sur un écran
/// de 340), mises à l'échelle de l'écran réel.
class WalletCard extends StatefulWidget {
  const WalletCard({super.key, required this.wallet, this.alignStart = false});

  final Wallet wallet;

  /// Carte calée à gauche (écran Portefeuille) au lieu de centrée (Accueil).
  final bool alignStart;

  @override
  State<WalletCard> createState() => _WalletCardState();
}

class _WalletCardState extends State<WalletCard> {
  static const _currencies = [Currency.cdf, Currency.usd];
  int _front = 0;
  bool _hidden = false;

  void _show(int index) {
    if (index != _front) setState(() => _front = index);
  }

  @override
  Widget build(BuildContext context) {
    final reduce = MediaQuery.disableAnimationsOf(context);
    final duration = Duration(milliseconds: reduce ? 0 : 350);
    final scale = (MediaQuery.sizeOf(context).width / 340)
        .clamp(.9, 1.35)
        .toDouble();
    return Column(
      crossAxisAlignment: widget.alignStart
          ? CrossAxisAlignment.start
          : CrossAxisAlignment.center,
      children: [
        GestureDetector(
          onHorizontalDragEnd: (details) {
            final v = details.primaryVelocity ?? 0;
            if (v < -100) _show(1);
            if (v > 100) _show(0);
          },
          child: SizedBox(
            width: 228 * scale + 30 * scale,
            height: 136 * scale,
            child: FittedBox(
              alignment: Alignment.centerLeft,
              child: SizedBox(
                width: 258,
                height: 136,
                child: Stack(
                  clipBehavior: Clip.none,
                  children: [
                    for (final index in [
                      for (var i = 0; i < _currencies.length; i++)
                        if (i != _front) i,
                      _front,
                    ])
                      AnimatedPositioned(
                        key: ValueKey(index),
                        duration: duration,
                        curve: Curves.ease,
                        left: widget.alignStart ? 0 : 15,
                        top: 0,
                        width: 228,
                        height: 136,
                        child: AnimatedSlide(
                          duration: duration,
                          curve: Curves.ease,
                          offset: Offset(index == _front ? 0 : 30 / 228, 0),
                          child: AnimatedScale(
                            duration: duration,
                            curve: Curves.ease,
                            scale: index == _front ? 1 : .88,
                            child: AnimatedOpacity(
                              duration: duration,
                              opacity: index == _front ? 1 : .5,
                              child: GestureDetector(
                                onTap: () => _show(index),
                                child: _card(
                                  context,
                                  _currencies[index],
                                  front: index == _front,
                                ),
                              ),
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ),
        ),
        const SizedBox(height: 12),
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            for (var i = 0; i < _currencies.length; i++)
              GestureDetector(
                onTap: () => _show(i),
                behavior: HitTestBehavior.opaque,
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 2.5,
                    vertical: 6,
                  ),
                  child: AnimatedContainer(
                    duration: duration,
                    width: 5,
                    height: 5,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: i == _front
                          ? context.palette.ink
                          : const Color(0xFFC9D0DB),
                    ),
                  ),
                ),
              ),
          ],
        ),
      ],
    );
  }

  Widget _card(BuildContext context, Currency currency, {required bool front}) {
    final l = AppLocalizations.of(context);
    final lang = langOf(context);
    final amount = widget.wallet.available[currency] ?? Money(0, currency);
    final secured = widget.wallet.secured[currency];
    final label = currency == Currency.cdf ? 'FC' : 'USD';
    String shown(Money money) =>
        _hidden ? '•••••• $label' : formatMoney(money, lang);
    final white = Colors.white;
    return DecoratedBox(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          stops: [0, .45, 1],
          colors: [
            NexisColors.halo,
            NexisColors.gradientStart,
            NexisColors.gradientEnd,
          ],
        ),
        boxShadow: front
            ? const [
                BoxShadow(
                  color: Color(0x8C0350E6),
                  offset: Offset(0, 18),
                  blurRadius: 30,
                  spreadRadius: -14,
                ),
              ]
            : null,
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: Stack(
          children: [
            // Les deux grands ovales discrets de la maquette.
            Positioned(
              right: -60,
              bottom: -90,
              width: 220,
              height: 170,
              child: _oval(Colors.white.withValues(alpha: .08)),
            ),
            Positioned(
              left: -40,
              bottom: -110,
              width: 240,
              height: 160,
              child: _oval(NexisColors.navy.withValues(alpha: .08)),
            ),
            if (front) ...[
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          'NEXIS HUB',
                          style: title(
                            8.5,
                            color: white.withValues(alpha: .9),
                          ).copyWith(letterSpacing: 1.9),
                        ),
                        const Spacer(),
                        Image.asset(
                          'assets/images/monogramme-blanc.png',
                          width: 18,
                          height: 19,
                          excludeFromSemantics: true,
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    Text(
                      '${l.available} · $label',
                      style: body(10.5, color: white.withValues(alpha: .85)),
                    ),
                    const SizedBox(height: 5),
                    FittedBox(
                      fit: BoxFit.scaleDown,
                      alignment: Alignment.centerLeft,
                      child: Text(
                        shown(amount),
                        style: title(
                          20,
                          color: white,
                        ).copyWith(letterSpacing: -.4),
                      ),
                    ),
                  ],
                ),
              ),
              Positioned(
                left: 16,
                right: 14,
                bottom: 13,
                child: Row(
                  children: [
                    if (secured != null && !secured.isZero) ...[
                      Icon(PhFill.shieldCheck, color: white, size: 13),
                      const SizedBox(width: 5),
                      Expanded(
                        child: Text(
                          l.securedAmount(shown(secured)),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: body(
                            10.5,
                            weight: FontWeight.w600,
                            color: white,
                          ),
                        ),
                      ),
                    ] else
                      const Spacer(),
                    Semantics(
                      button: true,
                      label: _hidden ? l.showAmounts : l.hideAmounts,
                      excludeSemantics: true,
                      child: GestureDetector(
                        onTap: () => setState(() => _hidden = !_hidden),
                        child: Container(
                          width: 32,
                          height: 32,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: white.withValues(alpha: .2),
                          ),
                          child: Icon(
                            _hidden ? PhRegular.eyeSlash : PhRegular.eye,
                            color: white,
                            size: 16,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _oval(Color color) => ClipOval(child: ColoredBox(color: color));
}
