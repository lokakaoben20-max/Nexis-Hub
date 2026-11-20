import 'package:flutter/material.dart';

import '../../app_state.dart';
import '../../data/models.dart';
import '../../data/money.dart';
import '../../l10n/app_localizations.dart';
import '../../ui/common.dart';
import '../../ui/dates.dart';
import '../../ui/icons.dart';
import '../../ui/loader.dart';
import '../../ui/parts.dart';
import '../../ui/theme.dart';
import '../shell.dart';
import 'report.dart';
import 'steps.dart';

const _violet = Color(0xFF494C95);

/// Le litige d'une mission : 26. en cours (l'argent bloqué, les étapes,
/// s'arranger) ou 27. la décision, selon ce que dit le serveur.
class DisputeScreen extends StatelessWidget {
  const DisputeScreen({super.key, required this.missionId});

  final int missionId;

  @override
  Widget build(BuildContext context) {
    final repo = AppScope.of(context).repository;
    return Loaded<(Mission, Dispute?)>(
      load: () async =>
          (await repo.mission(missionId), await repo.dispute(missionId)),
      builder: (context, data) {
        final (mission, dispute) = data;
        if (dispute == null) return const _NoDispute();
        return dispute.decided
            ? _DecisionView(mission: mission, dispute: dispute)
            : _OpenView(mission: mission, dispute: dispute);
      },
    );
  }
}

String _place(Mission mission, String lang) =>
    '${serviceName(mission.service, lang)} · ${mission.commune}';

String _firstName(Mission mission) =>
    mission.chosen?.firstName ?? mission.providerName?.split(' ').first ?? '';

class _NoDispute extends StatelessWidget {
  const _NoDispute();

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return NScreen(children: [NTopBar(title: l.disputeTitle)]);
  }
}

/// 26. Litige en cours.
class _OpenView extends StatelessWidget {
  const _OpenView({required this.mission, required this.dispute});

  final Mission mission;
  final Dispute dispute;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    final lang = langOf(context);
    final dark = Theme.of(context).brightness == Brightness.dark;
    final name = _firstName(mission);
    final reply = dispute.providerReply;
    return NScreen(
      bottom: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          NButton(
            label: l.writeNexis,
            icon: PhRegular.chatsCircle,
            onPressed: () => showComingSoon(context, l.writeNexis),
          ),
          const SizedBox(height: 10),
          NButton(
            label: l.weSettled,
            kind: NButtonKind.line,
            onPressed: () => showComingSoon(context, l.weSettled),
          ),
        ],
      ),
      children: [
        NTopBar(title: l.disputeTitle, subtitle: _place(mission, lang)),
        if (mission.amount != null)
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: dark ? const Color(0xFF2A1513) : const Color(0xFFFFF6F5),
              borderRadius: BorderRadius.circular(18),
              border: Border.all(
                color: dark ? const Color(0xFF5A2A25) : const Color(0xFFF6D3CF),
              ),
            ),
            child: Row(
              children: [
                Container(
                  width: 42,
                  height: 42,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: dark
                        ? const Color(0xFF3A1715)
                        : const Color(0xFFFDE8E6),
                  ),
                  child: const Icon(
                    PhFill.lockSimple,
                    size: 20,
                    color: Color(0xFFA1261B),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        formatMoney(mission.amount!, lang),
                        style: title(15, color: p.ink),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        l.nobodyTouches,
                        style: body(
                          12,
                          color: dark
                              ? const Color(0xFFFFB4AB)
                              : const Color(0xFF7A3A33),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                const PaymentPill(PaymentState.blocked, compact: true),
              ],
            ),
          ),
        NCard(
          child: StepList(
            items: [
              StepItem(
                l.youReported,
                sub:
                    '${disputeReasonText(l, dispute.reason)} · '
                    '${l.photosCount(dispute.photos)}',
                time: formatStamp(dispute.openedAt, lang),
                state: StepStatus.done,
              ),
              if (reply != null)
                StepItem(
                  l.providerReplied(name),
                  sub: lang == 'en' ? '“$reply”' : '« $reply »',
                  time: dispute.providerRepliedAt == null
                      ? null
                      : formatStamp(dispute.providerRepliedAt!, lang),
                  state: StepStatus.done,
                ),
              StepItem(
                l.nexisLooking,
                sub: l.nexisLookingSub,
                state: StepStatus.now,
              ),
              StepItem(
                l.decisionStep,
                sub: l.decisionStepSub,
                state: StepStatus.todo,
              ),
            ],
          ),
        ),
        NInfo(text: l.settleHint(name), icon: PhFill.info, violet: true),
      ],
    );
  }
}

/// 27. Décision : remboursé, versé au prestataire ou partagé. Les montants
/// viennent du serveur ; l'argent reste bloqué 3 jours pour contester.
class _DecisionView extends StatelessWidget {
  const _DecisionView({required this.mission, required this.dispute});

  final Mission mission;
  final Dispute dispute;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    final lang = langOf(context);
    final dark = Theme.of(context).brightness == Brightness.dark;
    final name = _firstName(mission);
    final outcome = dispute.outcome!;
    final left = dispute.contestUntil == null
        ? 0
        : daysLeft(dispute.contestUntil!);
    final (IconData icon, String heading, String text) = switch (outcome) {
      DisputeOutcome.refund => (
        PhRegular.arrowCounterClockwise,
        l.outcomeRefundTitle,
        l.outcomeRefundText(name),
      ),
      DisputeOutcome.release => (
        PhRegular.checkCircle,
        l.outcomeReleaseTitle(name),
        l.outcomeReleaseText(name),
      ),
      DisputeOutcome.split => (
        PhRegular.scales,
        l.outcomeSplitTitle,
        l.outcomeSplitText(name),
      ),
    };
    final violet = dark ? const Color(0xFFB3B5F2) : _violet;
    final line = dark ? p.line : const Color(0xFFEEF1F5);
    Widget amountRow(String label, Money money, {bool top = false}) =>
        Container(
          padding: EdgeInsets.only(top: top ? 10 : 0),
          decoration: top
              ? BoxDecoration(
                  border: Border(top: BorderSide(color: line)),
                )
              : null,
          child: Row(
            children: [
              Expanded(
                child: Text(
                  label,
                  style: body(15, weight: FontWeight.w700, color: p.ink),
                ),
              ),
              Text(formatMoney(money, lang), style: title(15, color: violet)),
            ],
          ),
        );
    final client = dispute.clientAmount;
    final provider = dispute.providerAmount;
    return NScreen(
      bottom: NButton(
        label: l.seeWallet,
        onPressed: () {
          Shell.requestedTab.value = Shell.walletTab;
          Navigator.of(context).popUntil((route) => route.isFirst);
        },
      ),
      children: [
        NTopBar(title: l.disputeOver),
        Column(
          children: [
            const SizedBox(height: 8),
            Container(
              width: 84,
              height: 84,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: dark ? const Color(0xFF22234A) : const Color(0xFFECECF8),
                boxShadow: [
                  BoxShadow(
                    color: dark ? p.surface : const Color(0xFFF4F4FB),
                    spreadRadius: 10,
                  ),
                ],
              ),
              child: Icon(icon, size: 36, color: violet),
            ),
            const SizedBox(height: 18),
            Text(
              heading,
              textAlign: TextAlign.center,
              style: title(19, color: p.ink).copyWith(height: 1.3),
            ),
            const SizedBox(height: 6),
            Text(
              text,
              textAlign: TextAlign.center,
              style: body(13, color: p.muted).copyWith(height: 1.5),
            ),
          ],
        ),
        NCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      _place(mission, lang),
                      style: body(13.5, color: p.muted),
                    ),
                  ),
                  if (mission.chosen?.slot != null)
                    Text(
                      formatSlot(mission.chosen!.slot, lang),
                      style: body(13.5, weight: FontWeight.w600, color: p.ink),
                    ),
                ],
              ),
              const SizedBox(height: 9),
              if (outcome != DisputeOutcome.release && client != null)
                amountRow(l.toRefundYou, client, top: true),
              if (outcome == DisputeOutcome.split && provider != null) ...[
                const SizedBox(height: 9),
                amountRow(l.forProvider(name), provider),
              ],
              if (outcome == DisputeOutcome.release && provider != null)
                amountRow(l.paidTo(name), provider, top: true),
              const SizedBox(height: 10),
              left > 0
                  ? Pill(
                      tone: PillTone.bad,
                      icon: PhFill.lockSimple,
                      text: l.blockedDaysLeft(left),
                    )
                  : PaymentPill(
                      outcome == DisputeOutcome.release
                          ? PaymentState.released
                          : PaymentState.refunded,
                    ),
            ],
          ),
        ),
        if (left > 0)
          NInfo(text: l.contestHint(left), icon: PhFill.info, violet: true),
      ],
    );
  }
}
