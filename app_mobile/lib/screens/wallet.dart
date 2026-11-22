import 'package:flutter/material.dart';

import '../app_state.dart';
import '../data/models.dart';
import '../data/money.dart';
import '../l10n/app_localizations.dart';
import '../ui/common.dart';
import '../ui/loader.dart';
import '../ui/nx_icon.dart';
import '../ui/nx_parts.dart';
import '../ui/theme.dart';
import '../ui/wallet_panel.dart';

/// 5. Portefeuille, d'après la maquette validée : la carte, trois actions,
/// puis les derniers mouvements de la devise choisie, chacun avec son état
/// en mots. Les montants et les états sont ceux du serveur.
class WalletScreen extends StatelessWidget {
  const WalletScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    final state = AppScope.of(context);
    final repo = state.repository;
    return ColoredBox(
      color: pageColor(context),
      child: SafeArea(
        bottom: false,
        child: Loaded<({Wallet wallet, List<Movement> movements})>(
          load: () async =>
              (wallet: await repo.wallet(), movements: await repo.movements()),
          builder: (context, data) {
            final movements = data.movements
                .where((m) => m.amount.currency == state.walletCurrency)
                .toList();
            return ListView(
              padding: const EdgeInsets.fromLTRB(18, 12, 18, 24),
              children: [
                Text(
                  l.navWallet,
                  style: title(21, color: p.ink).copyWith(letterSpacing: -.21),
                ),
                const SizedBox(height: 16),
                WalletPanel(wallet: data.wallet),
                const SizedBox(height: 18),
                Row(
                  children: [
                    _action(context, 'deposit', l.actionDeposit),
                    _action(context, 'withdraw', l.actionWithdraw),
                    _action(
                      context,
                      'history',
                      l.actionHistory,
                      onTap: () => showComingSoon(context, l.movements),
                    ),
                  ],
                ),
                const SizedBox(height: 22),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 2),
                  child: Text(
                    l.recentMovements,
                    style: body(15, weight: FontWeight.w600, color: p.ink),
                  ),
                ),
                const SizedBox(height: 10),
                for (final m in movements) ...[
                  _MovementTile(movement: m),
                  const SizedBox(height: 8),
                ],
              ],
            );
          },
        ),
      ),
    );
  }

  Widget _action(
    BuildContext context,
    String glyph,
    String label, {
    VoidCallback? onTap,
  }) {
    final p = context.palette;
    return Expanded(
      child: Semantics(
        button: true,
        label: label,
        excludeSemantics: true,
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: onTap ?? () => showComingSoon(context, label),
          child: Column(
            children: [
              Container(
                width: 52,
                height: 52,
                decoration: nxCard(context, radius: 18),
                alignment: Alignment.center,
                child: NxIcon(
                  glyph,
                  size: 26,
                  color: isDark(context) ? p.softInk : NexisColors.brand,
                ),
              ),
              const SizedBox(height: 7),
              Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: body(
                  12,
                  weight: FontWeight.w500,
                  color: mutedColor(context),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _MovementTile extends StatelessWidget {
  const _MovementTile({required this.movement});

  final Movement movement;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    final lang = langOf(context);
    final dark = isDark(context);
    final amount = AppScope.of(context).amountsHidden
        ? '•••• ${movement.amount.currency == Currency.cdf ? 'CDF' : 'USD'}'
        : '${movement.amount.minorUnits > 0 ? '+' : ''}${formatMoney(Money(movement.amount.minorUnits.abs(), movement.amount.currency), lang)}';
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
        : shortDate(context, movement.when);

    // Icône et couleur de la pastille de gauche.
    final (String glyph, Color bg, Color fg) = switch (movement.kind) {
      MovementKind.payment => (
        'lock',
        dark ? const Color(0xFF22234A) : const Color(0xFFEEEEF8),
        dark ? const Color(0xFFB3B5F2) : const Color(0xFF494C95),
      ),
      MovementKind.refund => (
        'refund',
        dark ? const Color(0xFF22234A) : const Color(0xFFEEEEF8),
        dark ? const Color(0xFFB3B5F2) : const Color(0xFF494C95),
      ),
      MovementKind.release => (
        'check',
        dark ? const Color(0xFF1A2740) : const Color(0xFFF0F3F8),
        dark ? const Color(0xFFA9B4C6) : const Color(0xFF4E5B70),
      ),
      MovementKind.deposit => (
        'moneyIn',
        dark ? const Color(0xFF12301F) : const Color(0xFFE6F4EA),
        dark ? const Color(0xFF5BD08A) : const Color(0xFF1E7A3C),
      ),
      MovementKind.withdrawal => (
        'moneyOut',
        dark ? const Color(0xFF1A2740) : const Color(0xFFF0F3F8),
        dark ? const Color(0xFFA9B4C6) : const Color(0xFF4E5B70),
      ),
    };
    final (StatusKind kind, String stateText) = switch (movement.state) {
      PaymentState.secured => (StatusKind.secured, l.paySecured),
      PaymentState.released => (StatusKind.done, l.payReleased),
      PaymentState.refunded => (StatusKind.secured, l.payRefunded),
      PaymentState.blocked => (StatusKind.bad, l.payBlocked),
      PaymentState.available => (StatusKind.done, l.payAvailable),
      PaymentState.none => (StatusKind.wait, ''),
    };

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: nxCard(context, radius: 18),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: bg,
              borderRadius: BorderRadius.circular(13),
            ),
            alignment: Alignment.center,
            child: NxIcon(glyph, size: 21, color: fg),
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
                Text(when, style: body(12.5, color: mutedColor(context))),
                if (stateText.isNotEmpty) ...[
                  const SizedBox(height: 7),
                  StatusChip(kind: kind, text: stateText, compact: true),
                ],
              ],
            ),
          ),
          const SizedBox(width: 8),
          Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Text(amount, maxLines: 1, style: title(13, color: p.ink)),
          ),
        ],
      ),
    );
  }
}
