import 'package:flutter/material.dart';

import '../../app_state.dart';
import '../../data/models.dart';
import '../../data/money.dart';
import '../../l10n/app_localizations.dart';
import '../../ui/common.dart';
import '../../ui/dates.dart';
import '../../ui/loader.dart';
import '../../ui/parts.dart';
import '../../ui/theme.dart';
import 'payment_pending.dart';

String operatorName(MobileOperator operator) => switch (operator) {
  MobileOperator.mpesa => 'M-Pesa',
  MobileOperator.orange => 'Orange Money',
  MobileOperator.airtel => 'Airtel Money',
};

/// Pastille de l'opérateur : une lettre en attendant l'accord des
/// opérateurs pour leurs logos.
Widget operatorBadge(MobileOperator operator) {
  final (letter, color) = switch (operator) {
    MobileOperator.mpesa => ('M', const Color(0xFFE60000)),
    MobileOperator.orange => ('O', const Color(0xFFFF7900)),
    MobileOperator.airtel => ('A', const Color(0xFFED1C24)),
  };
  return Container(
    width: 38,
    height: 38,
    alignment: Alignment.center,
    decoration: BoxDecoration(
      color: color,
      borderRadius: BorderRadius.circular(12),
    ),
    child: Text(
      letter,
      style: body(12, weight: FontWeight.w800, color: Colors.white),
    ),
  );
}

/// 4. Payer (maquette app-ecrans-v2) : le montant du devis enregistré,
/// le choix de l'opérateur, puis un seul bouton qui répète le montant.
class PayScreen extends StatefulWidget {
  const PayScreen({super.key, required this.mission, required this.quote});

  final Mission mission;
  final Quote quote;

  @override
  State<PayScreen> createState() => _PayScreenState();
}

class _PayScreenState extends State<PayScreen> {
  MobileOperator? _operator;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    final lang = langOf(context);
    final repo = AppScope.of(context).repository;
    final quote = widget.quote;
    final amount = formatMoney(quote.price, lang);
    return Loaded<List<PayAccount>>(
      load: repo.payAccounts,
      builder: (context, accounts) {
        final usable = accounts.where((a) => a.maskedNumber != null);
        final chosen =
            _operator ?? (usable.isEmpty ? null : usable.first.operator);
        return NScreen(
          bottom: NButton(
            label: l.payAmount(amount),
            onPressed: chosen == null
                ? null
                : () => Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (_) => PaymentPendingScreen(
                        mission: widget.mission,
                        quote: quote,
                        operator: chosen,
                      ),
                    ),
                  ),
          ),
          children: [
            NTopBar(title: l.payTitle),
            NCard(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 18),
              child: Column(
                children: [
                  ServiceBadge(widget.mission.service, size: 52),
                  const SizedBox(height: 10),
                  Text(
                    '${serviceName(widget.mission.service, lang)} · ${widget.mission.commune}',
                    style: body(14.5, weight: FontWeight.w700, color: p.ink),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    '${quote.providerName} · ${formatSlot(quote.slot, lang)}',
                    style: body(12.5, color: p.muted),
                  ),
                  const SizedBox(height: 8),
                  FittedBox(
                    child: Text(
                      amount,
                      style: title(
                        30,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            Text(
              l.payWith,
              style: body(15, weight: FontWeight.w600, color: p.ink),
            ),
            for (final account in accounts)
              _OperatorTile(
                account: account,
                selected: account.operator == chosen,
                onTap: account.maskedNumber == null
                    ? () => showComingSoon(context, l.addNumber)
                    : () => setState(() => _operator = account.operator),
              ),
            NInfo(text: l.paySecuredNote(quote.firstName)),
          ],
        );
      },
    );
  }
}

class _OperatorTile extends StatelessWidget {
  const _OperatorTile({
    required this.account,
    required this.selected,
    required this.onTap,
  });

  final PayAccount account;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    return Semantics(
      button: true,
      selected: selected,
      child: GestureDetector(
        onTap: onTap,
        child: NCard(
          selected: selected,
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          child: Row(
            children: [
              operatorBadge(account.operator),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      operatorName(account.operator),
                      style: body(14, weight: FontWeight.w700, color: p.ink),
                    ),
                    const SizedBox(height: 1),
                    Text(
                      account.maskedNumber ?? l.addNumber,
                      style: body(12, color: p.muted),
                    ),
                  ],
                ),
              ),
              Container(
                width: 20,
                height: 20,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: selected
                        ? NexisColors.brand
                        : const Color(0xFFC9D0DB),
                    width: selected ? 6 : 2,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
