import 'package:flutter/material.dart';

import '../data/models.dart';
import '../l10n/app_localizations.dart';
import '../ui/common.dart';
import '../ui/nx_icon.dart';
import '../ui/nx_parts.dart';
import '../ui/theme.dart';
import 'client/confirm.dart';
import 'client/dispute.dart';
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
    MissionStatus.disputed => DisputeScreen(missionId: mission.id),
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

/// Une mission, comme la maquette (design/app-accueil-frontend-design.html) :
/// pastille du service, prestataire avec sa note, montant et flèche, état en
/// clair, barre en trois temps pour une mission payée, et un bouton clair
/// quand il y a une suite (« Suivre la mission », « Comparer les devis »,
/// « Confirmer »). [showAction] est faux sur l'accueil, qui reste léger.
class MissionCard extends StatelessWidget {
  const MissionCard({super.key, required this.mission, this.showAction = true});

  final Mission mission;
  final bool showAction;

  /// Étapes franchies sur trois, d'après l'état et les étapes du serveur.
  int get _rail => switch (mission.status) {
    MissionStatus.confirmed => 1,
    MissionStatus.inProgress =>
      mission.steps.containsKey(TrackStep.onSite) ? 3 : 2,
    MissionStatus.awaitingConfirmation => 3,
    _ => 0,
  };

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    final lang = langOf(context);
    final dark = isDark(context);
    final amount = missionAmountText(mission, l, lang);
    final rating = mission.rating;
    final reviews = mission.reviews;

    final (
      StatusKind kind,
      String text,
      String? icon,
      bool pulse,
    ) = switch (mission.status) {
      MissionStatus.pending => (
        StatusKind.wait,
        l.statusPending,
        'clock',
        false,
      ),
      MissionStatus.quoted => (
        StatusKind.live,
        l.statusQuoted(mission.quotesCount),
        'check',
        false,
      ),
      MissionStatus.confirmed => (
        StatusKind.live,
        l.statusConfirmed,
        'check',
        false,
      ),
      MissionStatus.inProgress => (
        StatusKind.live,
        l.statusInProgress(mission.providerName ?? ''),
        null,
        true,
      ),
      MissionStatus.awaitingConfirmation => (
        StatusKind.warn,
        l.statusAwaiting,
        'alert',
        false,
      ),
      MissionStatus.completed => (
        StatusKind.done,
        mission.when == null
            ? l.statusCompleted
            : l.completedOn(shortDate(context, mission.when!)),
        'check',
        false,
      ),
      MissionStatus.cancelled => (
        StatusKind.wait,
        l.statusCancelled,
        null,
        false,
      ),
      MissionStatus.disputed => (
        StatusKind.bad,
        l.statusDisputed,
        'alert',
        false,
      ),
    };

    final String? action = !showAction
        ? null
        : switch (mission.status) {
            MissionStatus.confirmed ||
            MissionStatus.inProgress => l.followMission,
            MissionStatus.awaitingConfirmation => l.confirmAction,
            MissionStatus.quoted => l.compareQuotes,
            _ => null,
          };

    return Container(
      decoration: nxCard(context),
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
                    KnownServiceTile(mission.service),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            serviceName(mission.service, lang),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: body(
                              15,
                              weight: FontWeight.w600,
                              color: p.ink,
                            ),
                          ),
                          const SizedBox(height: 1),
                          if (mission.providerName == null)
                            Text(
                              mission.commune,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: body(13, color: mutedColor(context)),
                            )
                          else
                            Row(
                              children: [
                                Flexible(
                                  child: Text(
                                    mission.providerName!,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: body(13, color: mutedColor(context)),
                                  ),
                                ),
                                if (rating != null) ...[
                                  const SizedBox(width: 6),
                                  const NxIcon(
                                    'star',
                                    size: 13,
                                    color: Color(0xFFF2B53A),
                                  ),
                                  const SizedBox(width: 3),
                                  Text(
                                    ratingText(rating, lang),
                                    style: body(
                                      13,
                                      weight: FontWeight.w600,
                                      color: p.ink,
                                    ),
                                  ),
                                  if (reviews != null) ...[
                                    const SizedBox(width: 6),
                                    Flexible(
                                      child: Text(
                                        l.reviewsCount(reviews),
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                        style: body(
                                          13,
                                          color: faintColor(context),
                                        ),
                                      ),
                                    ),
                                  ],
                                ],
                              ],
                            ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 8),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        if (amount != null)
                          Text(
                            amount,
                            maxLines: 1,
                            style: title(14, color: p.ink),
                          ),
                        const SizedBox(height: 6),
                        NxIcon('chevron', size: 16, color: faintColor(context)),
                      ],
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                StatusChip(kind: kind, text: text, icon: icon, pulse: pulse),
                if (_rail > 0) ...[
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      for (var i = 0; i < 3; i++) ...[
                        if (i > 0) const SizedBox(width: 4),
                        Expanded(
                          child: Container(
                            height: 4,
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(2),
                              color: i < _rail
                                  ? (dark
                                        ? const Color(0xFF5B8CFF)
                                        : NexisColors.brand)
                                  : (dark ? p.line : const Color(0xFFE3E8F0)),
                            ),
                          ),
                        ),
                      ],
                    ],
                  ),
                ],
                if (action != null) ...[
                  const SizedBox(height: 12),
                  Semantics(
                    button: true,
                    child: GestureDetector(
                      onTap:
                          mission.status == MissionStatus.awaitingConfirmation
                          ? () => Navigator.of(context).push(
                              MaterialPageRoute<void>(
                                builder: (_) =>
                                    ConfirmScreen(missionId: mission.id),
                              ),
                            )
                          : () => openMission(context, mission),
                      child: Container(
                        height: 42,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                          color: p.soft,
                          borderRadius: BorderRadius.circular(14),
                        ),
                        child: Text(
                          action,
                          style: body(
                            14.5,
                            weight: FontWeight.w600,
                            color: dark ? p.softInk : const Color(0xFF0A3D9E),
                          ),
                        ),
                      ),
                    ),
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
