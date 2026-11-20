import 'package:flutter/material.dart';

import '../data/models.dart';
import '../data/money.dart';
import '../l10n/app_localizations.dart';
import 'common.dart';
import 'theme.dart';

/// Carte de solde unique. Le dernier choix de devise reste partagé entre
/// les écrans pendant toute la session de l'application.
class WalletCard extends StatefulWidget {
  const WalletCard({super.key, required this.wallet, this.alignStart = false});

  final Wallet wallet;
  final bool alignStart;

  @override
  State<WalletCard> createState() => _WalletCardState();
}

class _WalletCardState extends State<WalletCard> {
  static Currency _rememberedCurrency = Currency.cdf;
  late Currency _currency = _rememberedCurrency;
  bool _hidden = false;

  void _show(Currency currency) {
    if (_currency == currency) return;
    setState(() {
      _currency = currency;
      _rememberedCurrency = currency;
    });
  }

  @override
  Widget build(BuildContext context) {
    final reduce = MediaQuery.disableAnimationsOf(context);
    final duration = Duration(milliseconds: reduce ? 0 : 260);
    final l = AppLocalizations.of(context);
    final lang = langOf(context);
    final amount = widget.wallet.available[_currency] ?? Money(0, _currency);
    final secured = widget.wallet.secured[_currency] ?? Money(0, _currency);
    final label = _currency == Currency.cdf ? 'FC' : 'USD';
    final shownAmount = _hidden ? '•••••• $label' : _formatWalletMoney(amount, lang);
    final shownSecured =
        _hidden ? '•••••• $label' : _formatWalletMoney(secured, lang);

    return Align(
      alignment: widget.alignStart ? Alignment.centerLeft : Alignment.center,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 440),
        child: SizedBox(
          width: double.infinity,
          child: DecoratedBox(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(24),
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
              boxShadow: const [
                BoxShadow(
                  color: Color(0x660350E6),
                  offset: Offset(0, 16),
                  blurRadius: 28,
                  spreadRadius: -12,
                ),
              ],
            ),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(24),
              child: Stack(
                children: [
                  Positioned.fill(
                    child: ColoredBox(
                      color: NexisColors.navy.withValues(alpha: .2),
                    ),
                  ),
                  Positioned(
                    right: -48,
                    bottom: -88,
                    width: 220,
                    height: 175,
                    child: _oval(Colors.white.withValues(alpha: .08)),
                  ),
                  Positioned(
                    left: -70,
                    top: 60,
                    width: 200,
                    height: 180,
                    child: _oval(NexisColors.navy.withValues(alpha: .08)),
                  ),
                  Padding(
                    padding: const EdgeInsets.fromLTRB(20, 18, 18, 18),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Text(
                              'NEXIS HUB',
                              style: title(
                                9,
                                color: Colors.white.withValues(alpha: .92),
                              ).copyWith(letterSpacing: 1.8),
                            ),
                            const Spacer(),
                            Image.asset(
                              'assets/images/monogramme-blanc.png',
                              width: 20,
                              height: 21,
                              excludeFromSemantics: true,
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),
                        _currencySelector(l, duration),
                        const SizedBox(height: 16),
                        Text(
                          l.available,
                          style: body(
                            13,
                            weight: FontWeight.w500,
                            color: Colors.white.withValues(alpha: .94),
                          ),
                        ),
                        Row(
                          children: [
                            Expanded(
                              child: AnimatedSwitcher(
                                duration: duration,
                                switchInCurve: Curves.easeOut,
                                switchOutCurve: Curves.easeIn,
                                transitionBuilder: (child, animation) =>
                                    FadeTransition(
                                  opacity: animation,
                                  child: SlideTransition(
                                    position: Tween<Offset>(
                                      begin: const Offset(0, .08),
                                      end: Offset.zero,
                                    ).animate(animation),
                                    child: child,
                                  ),
                                ),
                                child: SizedBox(
                                  key: ValueKey(_currency),
                                  width: double.infinity,
                                  child: FittedBox(
                                    fit: BoxFit.scaleDown,
                                    alignment: Alignment.centerLeft,
                                    child: Text(
                                      shownAmount,
                                      maxLines: 1,
                                      style: title(31, color: Colors.white)
                                          .copyWith(letterSpacing: -.5),
                                    ),
                                  ),
                                ),
                              ),
                            ),
                            Semantics(
                              button: true,
                              label: _hidden ? l.showAmounts : l.hideAmounts,
                              child: IconButton(
                                tooltip:
                                    _hidden ? l.showAmounts : l.hideAmounts,
                                onPressed: () =>
                                    setState(() => _hidden = !_hidden),
                                constraints: const BoxConstraints.tightFor(
                                  width: 44,
                                  height: 44,
                                ),
                                padding: EdgeInsets.zero,
                                visualDensity: VisualDensity.standard,
                                icon: Icon(
                                  _hidden
                                      ? Icons.visibility_off
                                      : Icons.visibility,
                                  size: 19,
                                  color: Colors.white,
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.center,
                          children: [
                            Icon(
                              Icons.shield_outlined,
                              size: 17,
                              color: Colors.white,
                            ),
                            const SizedBox(width: 7),
                            Expanded(
                              child: AnimatedSwitcher(
                                duration: duration,
                                child: Text(
                                  l.walletLocked(shownSecured),
                                  key: ValueKey('locked-$_currency-$_hidden'),
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                  style: body(
                                    12.5,
                                    weight: FontWeight.w600,
                                    color: Colors.white,
                                  ),
                                ),
                              ),
                            ),
                            Tooltip(
                              message: l.walletExplanation,
                              triggerMode: TooltipTriggerMode.tap,
                              child: Semantics(
                                button: true,
                                label: l.walletInfoLabel,
                                child: SizedBox(
                                  width: 44,
                                  height: 44,
                                  child: Icon(
                                    Icons.info_outline,
                                    size: 19,
                                    color: Colors.white,
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                        Padding(
                          padding: const EdgeInsets.only(left: 24, right: 44),
                          child: Text(
                            l.walletExplanation,
                            style: body(
                              11.5,
                              color: Colors.white.withValues(alpha: .92),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _currencySelector(AppLocalizations l, Duration duration) {
    return Container(
      height: 48,
      padding: const EdgeInsets.all(3),
      decoration: BoxDecoration(
        color: NexisColors.navy.withValues(alpha: .26),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white.withValues(alpha: .22)),
      ),
      child: Row(
        children: [
          _currencyButton(Currency.cdf, duration),
          _currencyButton(Currency.usd, duration),
        ],
      ),
    );
  }

  Widget _currencyButton(Currency currency, Duration duration) {
    final selected = currency == _currency;
    final label = currency == Currency.cdf ? 'CDF' : 'USD';
    return Expanded(
      child: Semantics(
        button: true,
        selected: selected,
        label: label,
        child: Material(
          color: selected ? Colors.white : Colors.transparent,
          borderRadius: BorderRadius.circular(11),
          child: InkWell(
            onTap: () => _show(currency),
            borderRadius: BorderRadius.circular(11),
            child: SizedBox(
              height: 42,
              child: Center(
                child: AnimatedDefaultTextStyle(
                  duration: duration,
                  style: body(
                    13,
                    weight: FontWeight.w700,
                    color: selected ? NexisColors.navy : Colors.white,
                  ),
                  child: Text(label),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  String _formatWalletMoney(Money money, String languageCode) {
    final formatted = formatMoney(money, languageCode);
    if (languageCode != 'en') return formatted;
    return formatted.replaceAllMapped(
      RegExp(r'(?<=\d),(?=\d{3}(?:[.,]| |$))'),
      (_) => ' ',
    );
  }

  Widget _oval(Color color) => ClipOval(child: ColoredBox(color: color));
}
