import 'package:flutter/material.dart';

import '../data/models.dart';
import '../data/money.dart';
import '../l10n/app_localizations.dart';
import '../ui/common.dart';
import '../ui/theme.dart';

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

/// Une mission dans « Mes missions » : service, état, argent, action.
class MissionCard extends StatelessWidget {
  const MissionCard({super.key, required this.mission});

  final Mission mission;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    final lang = langOf(context);
    final title = '${serviceName(mission.service, lang)} · ${mission.commune}';
    final action = switch (mission.status) {
      MissionStatus.quoted => l.compareQuotes,
      MissionStatus.inProgress || MissionStatus.confirmed => l.follow,
      _ => null,
    };
    return Material(
      color: p.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: BorderSide(color: p.line),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(18),
        onTap: () => showComingSoon(context, title),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  ServiceBadge(mission.service, size: 42),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          title,
                          style: body(
                            15,
                            weight: FontWeight.w600,
                            color: p.ink,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          missionStatusText(l, mission),
                          style: body(13, color: p.muted),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          mission.reference,
                          style: body(12, color: p.muted),
                        ),
                      ],
                    ),
                  ),
                  if (mission.amount != null)
                    Text(
                      formatMoney(mission.amount!, lang),
                      style: body(14, weight: FontWeight.w700, color: p.ink),
                    ),
                ],
              ),
              if (mission.payment != PaymentState.none) ...[
                const SizedBox(height: 10),
                PaymentPill(mission.payment),
              ],
              if (action != null) ...[
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.tonal(
                    onPressed: () => showComingSoon(context, action),
                    style: FilledButton.styleFrom(
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    child: Text(
                      action,
                      style: body(14, weight: FontWeight.w600),
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
