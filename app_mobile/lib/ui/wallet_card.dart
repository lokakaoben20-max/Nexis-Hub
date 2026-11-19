import 'package:flutter/material.dart';

import 'icons.dart';

import '../data/models.dart';
import '../data/money.dart';
import '../l10n/app_localizations.dart';
import 'common.dart';
import 'theme.dart';

/// Carte portefeuille A : FC puis USD en glissant, l'œil masque les montants.
class WalletCard extends StatefulWidget {
  const WalletCard({super.key, required this.wallet});

  final Wallet wallet;

  @override
  State<WalletCard> createState() => _WalletCardState();
}

class _WalletCardState extends State<WalletCard> {
  final _pages = PageController(viewportFraction: .86);
  int _page = 0;
  bool _hidden = false;

  @override
  void dispose() {
    _pages.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    const currencies = [Currency.cdf, Currency.usd];
    return Column(
      children: [
        SizedBox(
          height: 176,
          child: PageView.builder(
            controller: _pages,
            itemCount: currencies.length,
            onPageChanged: (page) => setState(() => _page = page),
            itemBuilder: (context, index) => Padding(
              padding: const EdgeInsets.symmetric(horizontal: 6),
              child: _card(context, currencies[index]),
            ),
          ),
        ),
        const SizedBox(height: 10),
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            for (var i = 0; i < currencies.length; i++)
              AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                width: i == _page ? 16 : 6,
                height: 6,
                margin: const EdgeInsets.symmetric(horizontal: 3),
                decoration: BoxDecoration(
                  color: i == _page ? NexisColors.brand : context.palette.line,
                  borderRadius: BorderRadius.circular(9),
                ),
              ),
          ],
        ),
      ],
    );
  }

  Widget _card(BuildContext context, Currency currency) {
    final l = AppLocalizations.of(context);
    final lang = langOf(context);
    final amount = widget.wallet.available[currency] ?? Money(0, currency);
    final secured = widget.wallet.secured[currency];
    final label = currency == Currency.cdf ? 'FC' : 'USD';
    String shown(Money money) =>
        _hidden ? '••••• $label' : formatMoney(money, lang);
    return Container(
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [NexisColors.halo, NexisColors.gradientEnd],
        ),
        borderRadius: BorderRadius.circular(22),
        boxShadow: [
          BoxShadow(
            color: NexisColors.gradientEnd.withValues(alpha: .28),
            blurRadius: 18,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      padding: const EdgeInsets.fromLTRB(18, 16, 12, 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                'NEXIS HUB',
                style: body(
                  11,
                  weight: FontWeight.w700,
                  color: Colors.white,
                ).copyWith(letterSpacing: 1.6),
              ),
              const Spacer(),
              Image.asset(
                'assets/images/monogramme-blanc.png',
                width: 22,
                height: 22,
                excludeFromSemantics: true,
              ),
              const SizedBox(width: 6),
            ],
          ),
          const SizedBox(height: 14),
          Text(
            '${l.available} · $label',
            style: body(12.5, color: Colors.white.withValues(alpha: .85)),
          ),
          const SizedBox(height: 2),
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(shown(amount), style: title(30, color: Colors.white)),
          ),
          const Spacer(),
          Row(
            children: [
              if (secured != null && !secured.isZero) ...[
                const Icon(PhFill.shieldCheck, color: Colors.white, size: 15),
                const SizedBox(width: 5),
                Expanded(
                  child: Text(
                    l.securedAmount(shown(secured)),
                    style: body(
                      12.5,
                      weight: FontWeight.w600,
                      color: Colors.white,
                    ),
                  ),
                ),
              ] else
                const Spacer(),
              IconButton(
                tooltip: _hidden ? l.showAmounts : l.hideAmounts,
                onPressed: () => setState(() => _hidden = !_hidden),
                style: IconButton.styleFrom(
                  backgroundColor: Colors.white.withValues(alpha: .18),
                ),
                icon: Icon(
                  _hidden ? PhRegular.eyeSlash : PhRegular.eye,
                  color: Colors.white,
                  size: 20,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
