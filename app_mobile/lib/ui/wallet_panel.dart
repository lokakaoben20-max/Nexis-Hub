import 'package:flutter/material.dart';

import '../app_state.dart';
import '../data/models.dart';
import '../data/money.dart';
import '../l10n/app_localizations.dart';
import 'common.dart';
import 'nx_icon.dart';
import 'theme.dart';

/// Carte de portefeuille de la maquette validée
/// (design/app-accueil-frontend-design.html) : une seule carte, bascule
/// CDF / USD dedans, le disponible en grand, puis « bloqués pour vos
/// missions en cours » avec son (i). Les montants sont ceux du serveur :
/// rien n'est calculé ici. La devise choisie et le masquage sont partagés
/// entre l'accueil et l'écran Portefeuille.
class WalletPanel extends StatefulWidget {
  const WalletPanel({super.key, required this.wallet});

  final Wallet wallet;

  @override
  State<WalletPanel> createState() => _WalletPanelState();
}

class _WalletPanelState extends State<WalletPanel> {
  bool _tip = false;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final lang = langOf(context);
    final state = AppScope.of(context);
    final currency = state.walletCurrency;
    final hidden = state.amountsHidden;
    final reduce = MediaQuery.disableAnimationsOf(context);
    final code = currency == Currency.cdf ? 'CDF' : 'USD';
    final available = widget.wallet.available[currency] ?? Money(0, currency);
    final held = widget.wallet.secured[currency];
    String shown(Money m) => hidden ? '•••• $code' : formatMoney(m, lang);
    const white = Colors.white;

    return DecoratedBox(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(26),
        gradient: const LinearGradient(
          // 150deg de la maquette.
          begin: Alignment(-.5, -.87),
          end: Alignment(.5, .87),
          stops: [0, .55, 1],
          colors: [Color(0xFF0A63F0), Color(0xFF0350E6), Color(0xFF0340B8)],
        ),
        boxShadow: const [
          BoxShadow(
            color: Color(0xA60350E6),
            offset: Offset(0, 22),
            blurRadius: 34,
            spreadRadius: -18,
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(26),
        child: Stack(
          children: [
            // Les trois barres du logo en filigrane.
            const Positioned(
              right: 20,
              top: 62,
              width: 62,
              height: 66,
              child: ExcludeSemantics(
                child: CustomPaint(painter: _BarsPainter()),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(18, 16, 18, 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      _CurrencySwitch(
                        selected: currency,
                        label: l.currency,
                        onChanged: state.setWalletCurrency,
                      ),
                      const Spacer(),
                      Semantics(
                        button: true,
                        label: hidden ? l.showAmounts : l.hideAmounts,
                        excludeSemantics: true,
                        child: GestureDetector(
                          behavior: HitTestBehavior.opaque,
                          onTap: () => state.setAmountsHidden(!hidden),
                          child: SizedBox(
                            width: 30,
                            height: 30,
                            child: Center(
                              child: NxIcon(
                                hidden ? 'eyeOff' : 'eye',
                                size: 18,
                                color: white.withValues(alpha: .85),
                              ),
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  Text(
                    l.available,
                    style: body(13, color: white.withValues(alpha: .85)),
                  ),
                  const SizedBox(height: 2),
                  FittedBox(
                    fit: BoxFit.scaleDown,
                    alignment: Alignment.centerLeft,
                    child: Text(
                      shown(available),
                      maxLines: 1,
                      style: title(32, color: white, height: 1.1).copyWith(
                        letterSpacing: -.64,
                        fontFeatures: const [FontFeature.tabularFigures()],
                      ),
                    ),
                  ),
                  if (held != null && !held.isZero) ...[
                    const SizedBox(height: 14),
                    Container(
                      padding: const EdgeInsets.only(top: 12),
                      decoration: BoxDecoration(
                        border: Border(
                          top: BorderSide(color: white.withValues(alpha: .22)),
                        ),
                      ),
                      child: Row(
                        children: [
                          const NxIcon('lock', size: 16, color: white),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              l.heldForMissions(shown(held)),
                              style: body(13, color: white, height: 1.3),
                            ),
                          ),
                          Semantics(
                            button: true,
                            label: l.heldWhy,
                            expanded: _tip,
                            excludeSemantics: true,
                            child: GestureDetector(
                              behavior: HitTestBehavior.opaque,
                              onTap: () => setState(() => _tip = !_tip),
                              child: const SizedBox(
                                width: 34,
                                height: 30,
                                child: Align(
                                  alignment: Alignment.centerRight,
                                  child: NxIcon('info', size: 17, color: white),
                                ),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                    // Durée nulle (animations réduites) : pas d'AnimatedSize,
                    // qui ne supporte pas une durée à zéro.
                    if (reduce)
                      _tipBox(l, white)
                    else
                      AnimatedSize(
                        duration: const Duration(milliseconds: 200),
                        alignment: Alignment.topCenter,
                        child: _tipBox(l, white),
                      ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

extension on _WalletPanelState {
  Widget _tipBox(AppLocalizations l, Color white) => _tip
      ? Container(
          margin: const EdgeInsets.only(top: 10),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          width: double.infinity,
          decoration: BoxDecoration(
            color: const Color(0x52021937),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Text(l.heldTip, style: body(12.5, color: white, height: 1.45)),
        )
      : const SizedBox(width: double.infinity);
}

class _CurrencySwitch extends StatelessWidget {
  const _CurrencySwitch({
    required this.selected,
    required this.label,
    required this.onChanged,
  });

  final Currency selected;
  final String label;
  final ValueChanged<Currency> onChanged;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      container: true,
      label: label,
      child: Container(
        padding: const EdgeInsets.all(3),
        decoration: BoxDecoration(
          color: const Color(0x47021937),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            for (final (c, text) in const [
              (Currency.cdf, 'CDF'),
              (Currency.usd, 'USD'),
            ])
              Semantics(
                button: true,
                selected: c == selected,
                child: GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onTap: () => onChanged(c),
                  child: Container(
                    height: 28,
                    padding: const EdgeInsets.symmetric(horizontal: 13),
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: c == selected ? Colors.white : Colors.transparent,
                      borderRadius: BorderRadius.circular(9),
                    ),
                    child: Text(
                      text,
                      style: body(
                        13,
                        weight: FontWeight.w600,
                        color: c == selected
                            ? NexisColors.brand
                            : Colors.white.withValues(alpha: .78),
                        height: 1.2,
                      ),
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// Les trois barres du logo (viewBox 513 487 973 1026 de la maquette),
/// en blanc à 16 %.
class _BarsPainter extends CustomPainter {
  const _BarsPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final path = Path();
    for (final top in const [487.0, 900.0, 1313.0]) {
      path
        ..moveTo(513, top)
        ..lineTo(1486, top)
        ..lineTo(1364, top + 200)
        ..lineTo(513, top + 200)
        ..close();
    }
    canvas.scale(size.width / 973, size.height / 1026);
    canvas.translate(-513, -487);
    canvas.drawPath(path, Paint()..color = Colors.white.withValues(alpha: .16));
  }

  @override
  bool shouldRepaint(_BarsPainter old) => false;
}
