import 'package:flutter/material.dart';

import '../ui/icons.dart';

import '../app_state.dart';
import '../data/models.dart';
import '../data/money.dart';
import '../l10n/app_localizations.dart';
import '../ui/common.dart';
import '../ui/loader.dart';
import '../ui/theme.dart';
import '../ui/wallet_card.dart';

/// 5. Portefeuille : la carte, Dépôt et Retrait, puis chaque mouvement
/// avec son état en mots.
class WalletScreen extends StatelessWidget {
  const WalletScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    final repo = AppScope.of(context).repository;
    return SafeArea(
      bottom: false,
      child: Loaded<({Wallet wallet, List<Movement> movements})>(
        load: () async =>
            (wallet: await repo.wallet(), movements: await repo.movements()),
        builder: (context, data) => ListView(
          padding: const EdgeInsets.fromLTRB(0, 20, 0, 24),
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Text(l.navWallet, style: title(26, color: p.ink)),
            ),
            const SizedBox(height: 14),
            WalletCard(wallet: data.wallet),
            const SizedBox(height: 16),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Row(
                children: [
                  Expanded(
                    child: _button(context, PhBold.arrowDown, l.actionDeposit),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: _button(context, PhBold.arrowUp, l.actionWithdraw),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 22),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Text(l.movements, style: title(15, color: p.ink)),
            ),
            const SizedBox(height: 10),
            Container(
              margin: const EdgeInsets.symmetric(horizontal: 20),
              decoration: BoxDecoration(
                color: p.surface,
                borderRadius: BorderRadius.circular(18),
                border: Border.all(color: p.line),
              ),
              child: Column(
                children: [
                  for (var i = 0; i < data.movements.length; i++) ...[
                    if (i > 0) Divider(height: 1, color: p.line),
                    _movement(context, data.movements[i]),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _button(BuildContext context, IconData icon, String label) =>
      FilledButton.tonalIcon(
        onPressed: () => showComingSoon(context, label),
        icon: Icon(icon, size: 18),
        label: Text(label, style: title(14)),
        style: FilledButton.styleFrom(
          minimumSize: const Size.fromHeight(50),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
          ),
        ),
      );

  Widget _movement(BuildContext context, Movement movement) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    final lang = langOf(context);
    final now = DateTime.now();
    final days = DateTime(now.year, now.month, now.day)
        .difference(
          DateTime(movement.when.year, movement.when.month, movement.when.day),
        )
        .inDays;
    final when = days == 0
        ? l.today
        : days == 1
        ? l.yesterday
        : MaterialLocalizations.of(context).formatShortMonthDay(movement.when);
    final icon = switch (movement.kind) {
      MovementKind.payment => PhRegular.shieldCheck,
      MovementKind.refund => PhRegular.arrowCounterClockwise,
      MovementKind.release => PhRegular.checkCircle,
      MovementKind.deposit => PhRegular.arrowDown,
      MovementKind.withdrawal => PhRegular.arrowUp,
    };
    return Padding(
      padding: const EdgeInsets.all(14),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(color: p.soft, shape: BoxShape.circle),
            child: Icon(icon, color: p.softInk, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  movement.label,
                  style: body(14.5, weight: FontWeight.w600, color: p.ink),
                ),
                Text(when, style: body(12.5, color: p.muted)),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                formatMoney(movement.amount, lang),
                style: body(14.5, weight: FontWeight.w700, color: p.ink),
              ),
              const SizedBox(height: 4),
              PaymentPill(movement.state),
            ],
          ),
        ],
      ),
    );
  }
}
