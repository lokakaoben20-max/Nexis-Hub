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
          padding: const EdgeInsets.fromLTRB(0, 16, 0, 24),
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 18),
              child: Text(l.navWallet, style: title(22, color: p.ink)),
            ),
            const SizedBox(height: 14),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 18),
              child: WalletCard(wallet: data.wallet, alignStart: true),
            ),
            const SizedBox(height: 18),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 18),
              child: Row(
                children: [
                  Expanded(
                    child: _button(
                      context,
                      PhRegular.arrowFatLineDown,
                      l.actionDeposit,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: _button(
                      context,
                      PhRegular.arrowFatLineUp,
                      l.actionWithdraw,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 18),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 18),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.baseline,
                textBaseline: TextBaseline.alphabetic,
                children: [
                  Expanded(
                    child: Text(
                      l.movements,
                      style: body(15, weight: FontWeight.w600, color: p.ink),
                    ),
                  ),
                  GestureDetector(
                    onTap: () => showComingSoon(context, l.movements),
                    child: Text(
                      l.seeAll,
                      style: body(
                        12.5,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 14),
            Container(
              margin: const EdgeInsets.symmetric(horizontal: 18),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
              decoration: BoxDecoration(
                color: p.surface,
                borderRadius: BorderRadius.circular(20),
                border: Border.all(
                  color: Theme.of(context).brightness == Brightness.dark
                      ? p.line
                      : const Color(0xFFEEF1F5),
                ),
              ),
              child: Column(
                children: [
                  for (var i = 0; i < data.movements.length; i++) ...[
                    if (i > 0)
                      Divider(
                        height: 1,
                        thickness: 1,
                        color: Theme.of(context).brightness == Brightness.dark
                            ? p.line
                            : const Color(0xFFEEF1F5),
                      ),
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

  Widget _button(BuildContext context, IconData icon, String label) {
    final p = context.palette;
    return Semantics(
      button: true,
      child: GestureDetector(
        onTap: () => showComingSoon(context, label),
        child: Container(
          height: 50,
          decoration: BoxDecoration(
            color: p.soft,
            borderRadius: BorderRadius.circular(16),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, size: 20, color: p.softInk),
              const SizedBox(width: 8),
              Text(label, style: title(14.5, color: p.softInk)),
            ],
          ),
        ),
      ),
    );
  }

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
    final dark = Theme.of(context).brightness == Brightness.dark;
    final (IconData icon, Color bg, Color fg) = switch (movement.kind) {
      MovementKind.payment => (PhFill.shieldCheck, p.soft, p.softInk),
      MovementKind.refund => (
        PhRegular.arrowCounterClockwise,
        dark ? const Color(0xFF22234A) : const Color(0xFFECECF8),
        dark ? const Color(0xFFB3B5F2) : NexisColors.violet,
      ),
      MovementKind.release => (
        PhFill.checkCircle,
        dark ? const Color(0xFF12301F) : const Color(0xFFE3F5EA),
        dark ? const Color(0xFF5BD08A) : NexisColors.ok,
      ),
      MovementKind.deposit => (PhRegular.arrowDown, p.soft, p.softInk),
      MovementKind.withdrawal => (PhRegular.arrowUp, p.soft, p.softInk),
    };
    final amount = movement.amount;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 10),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(color: bg, shape: BoxShape.circle),
            child: Icon(icon, color: fg, size: 19),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  movement.label,
                  style: body(14, weight: FontWeight.w700, color: p.ink),
                ),
                const SizedBox(height: 3),
                Text(
                  when,
                  style: body(
                    12,
                    color: dark ? p.muted : const Color(0xFF5B667A),
                  ),
                ),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                formatMoney(
                  Money(amount.minorUnits.abs(), amount.currency),
                  lang,
                ),
                style: title(13, color: p.ink),
              ),
              const SizedBox(height: 3),
              PaymentPill(movement.state, compact: true),
            ],
          ),
        ],
      ),
    );
  }
}
