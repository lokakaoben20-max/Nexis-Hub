import 'package:flutter/material.dart';

import '../data/models.dart';
import '../ui/icons.dart';
import '../data/money.dart';
import '../l10n/app_localizations.dart';
import '../ui/common.dart';
import '../ui/theme.dart';
import 'client/confirm.dart';
import 'client/quotes.dart';
import 'client/tracking.dart';

String missionStatusText(AppLocalizations l, Mission mission) =>
    switch (mission.status) {
      MissionStatus.pending => l.statusPending,
      MissionStatus.quoted => l.statusQuoted(mission.quotesCount),
      MissionStatus.confirmed => l.statusConfirmed,
      MissionStatus.inProgress => l.statusInProgress(
        mission.providerName ?? '',
      ),
      MissionStatus.awaitingConfirmation => l.statusAwaiting,
      MissionStatus.completed => l.statusCompleted,
      MissionStatus.cancelled => l.statusCancelled,
      MissionStatus.disputed => l.statusDisputed,
    };

/// Ouvre l'écran qui correspond à l'état de la mission.
void openMission(BuildContext context, Mission mission) {
  final Widget? screen = switch (mission.status) {
    MissionStatus.quoted => QuotesScreen(mission: mission),
    MissionStatus.confirmed ||
    MissionStatus.inProgress ||
    MissionStatus.awaitingConfirmation => TrackingScreen(missionId: mission.id),
    _ => null,
  };
  if (screen == null) {
    final lang = langOf(context);
    showComingSoon(
      context,
      '${serviceName(mission.service, lang)} · ${mission.commune}',
    );
    return;
  }
  Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => screen));
}

/// Une mission dans « Mes missions », comme la maquette (app-ecrans-v2) :
/// service, état et pastille à droite ; barre d'avancement et « Suivre »
/// pour une mission en cours ; « Comparer les devis » quand des devis
/// sont arrivés.
class MissionCard extends StatelessWidget {
  const MissionCard({super.key, required this.mission});

  final Mission mission;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final lang = langOf(context);
    final grey = dark ? p.muted : const Color(0xFF5B667A);
    final title = '${serviceName(mission.service, lang)} · ${mission.commune}';
    final following =
        mission.status == MissionStatus.inProgress ||
        mission.status == MissionStatus.confirmed;
    final Widget? pill = switch (mission.status) {
      MissionStatus.quoted => Pill(
        tone: PillTone.warn,
        icon: PhRegular.clock,
        text: l.quotesPill(mission.quotesCount),
      ),
      MissionStatus.pending => Pill(
        tone: PillTone.wait,
        icon: PhRegular.clock,
        text: l.waitingPill,
      ),
      _
          when mission.payment == PaymentState.secured &&
              mission.amount != null =>
        PaymentPill(
          PaymentState.secured,
          text: formatMoney(mission.amount!, lang),
        ),
      _ when mission.payment != PaymentState.none => PaymentPill(
        mission.payment,
      ),
      _ => null,
    };
    return Container(
      decoration: BoxDecoration(
        color: p.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: dark ? p.line : const Color(0xFFEEF1F5)),
      ),
      child: Material(
        type: MaterialType.transparency,
        child: InkWell(
          borderRadius: BorderRadius.circular(20),
          onTap: () => openMission(context, mission),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    ServiceBadge(mission.service, size: 44),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            title,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: body(
                              14.5,
                              weight: FontWeight.w700,
                              color: p.ink,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            missionStatusText(l, mission),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: body(12.5, color: grey),
                          ),
                        ],
                      ),
                    ),
                    if (pill != null) ...[const SizedBox(width: 8), pill],
                  ],
                ),
                if (following) ...[
                  const SizedBox(height: 10),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(3),
                    child: SizedBox(
                      height: 6,
                      child: Stack(
                        children: [
                          Positioned.fill(
                            child: ColoredBox(
                              color: dark ? p.line : const Color(0xFFEEF1F5),
                            ),
                          ),
                          const Align(
                            alignment: Alignment.centerLeft,
                            child: FractionallySizedBox(
                              widthFactor: .6,
                              heightFactor: 1,
                              child: DecoratedBox(
                                decoration: BoxDecoration(
                                  borderRadius: BorderRadius.all(
                                    Radius.circular(3),
                                  ),
                                  gradient: LinearGradient(
                                    colors: [
                                      NexisColors.halo,
                                      NexisColors.gradientEnd,
                                    ],
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          mission.reference,
                          style: body(
                            11.5,
                            weight: FontWeight.w500,
                            color: grey,
                          ),
                        ),
                      ),
                      Text(
                        l.follow,
                        style: body(11.5, weight: FontWeight.w500, color: grey),
                      ),
                    ],
                  ),
                ],
                if (mission.status == MissionStatus.awaitingConfirmation) ...[
                  const SizedBox(height: 10),
                  _SmallButton(
                    label: l.confirmAction,
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => ConfirmScreen(missionId: mission.id),
                      ),
                    ),
                  ),
                ],
                if (mission.status == MissionStatus.quoted) ...[
                  const SizedBox(height: 10),
                  _SmallButton(
                    label: l.compareQuotes,
                    onTap: () => openMission(context, mission),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Petit bouton en dégradé, calé à gauche (« Comparer les devis »).
class _SmallButton extends StatelessWidget {
  const _SmallButton({required this.label, required this.onTap});

  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: AlignmentDirectional.centerStart,
      child: Semantics(
        button: true,
        child: GestureDetector(
          onTap: onTap,
          child: Container(
            height: 38,
            padding: const EdgeInsets.symmetric(horizontal: 14),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(12),
              gradient: const LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [NexisColors.halo, NexisColors.gradientEnd],
              ),
            ),
            child: Center(
              widthFactor: 1,
              child: Text(label, style: title(12.5, color: Colors.white)),
            ),
          ),
        ),
      ),
    );
  }
}
