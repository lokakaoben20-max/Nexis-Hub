import 'package:flutter/material.dart';

import '../../app_state.dart';
import '../../data/models.dart';
import '../../l10n/app_localizations.dart';
import '../../ui/common.dart';
import '../../ui/dates.dart';
import '../../ui/icons.dart';
import '../../ui/loader.dart';
import '../../ui/parts.dart';
import '../../ui/theme.dart';
import 'confirm.dart';
import 'steps.dart';

/// 6. Suivi de mission (maquette app-ecrans-v3) : la distance du
/// prestataire s'il partage sa position (pas d'heure d'arrivée en v1),
/// puis chaque étape.
class TrackingScreen extends StatelessWidget {
  const TrackingScreen({super.key, required this.missionId});

  final int missionId;

  @override
  Widget build(BuildContext context) {
    final repo = AppScope.of(context).repository;
    return Loaded<Mission>(
      load: () => repo.mission(missionId),
      builder: (context, mission) => _build(context, mission),
    );
  }

  Widget _build(BuildContext context, Mission mission) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    final lang = langOf(context);
    final quote = mission.chosen;
    final name = quote?.firstName ?? mission.providerName ?? '';
    final steps = mission.steps;
    const order = TrackStep.values;
    // Comme la maquette : la dernière étape atteinte est « en cours »,
    // celles d'avant sont faites ; la confirmation, une fois là, est faite.
    final reached = order.where(steps.containsKey).toList();
    final current = reached.isEmpty ? null : reached.last;
    final sharing = mission.distanceKm != null && current == TrackStep.onTheWay;
    StepStatus stateOf(TrackStep s) => !steps.containsKey(s)
        ? StepStatus.todo
        : s == current && s != TrackStep.confirmed
        ? StepStatus.now
        : StepStatus.done;
    String? time(TrackStep s) =>
        steps[s] == null ? null : formatClock(steps[s]!, lang);
    final km = mission.distanceKm == null
        ? ''
        : (lang == 'en'
              ? mission.distanceKm!.toStringAsFixed(1)
              : mission.distanceKm!.toStringAsFixed(1).replaceAll('.', ','));

    return NScreen(
      bottom: mission.status == MissionStatus.awaitingConfirmation
          ? NButton(
              label: l.confirmAction,
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => ConfirmScreen(missionId: mission.id),
                ),
              ),
            )
          : null,
      children: [
        NTopBar(
          title: l.trackTitle,
          subtitle:
              '${serviceName(mission.service, lang)} · ${mission.commune}',
        ),
        ClipRRect(
          borderRadius: BorderRadius.circular(20),
          child: SizedBox(
            height: 190,
            child: Stack(
              children: [
                Positioned.fill(
                  child: CustomPaint(painter: _MapPainter(sharing: sharing)),
                ),
                Positioned(
                  left: 12,
                  top: 12,
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 11,
                      vertical: 6,
                    ),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(99),
                      boxShadow: const [
                        BoxShadow(
                          color: Color(0x1F021937),
                          offset: Offset(0, 1),
                          blurRadius: 3,
                        ),
                      ],
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          sharing ? PhFill.navigationArrow : PhRegular.mapPin,
                          size: 14,
                          color: NexisColors.brand,
                        ),
                        const SizedBox(width: 6),
                        Text(
                          sharing ? l.distanceAway(name, km) : l.trackingOff,
                          style: body(
                            12,
                            weight: FontWeight.w600,
                            color: NexisColors.navy,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
        if (quote != null)
          NCard(
            child: Row(
              children: [
                NAvatar(
                  initials: quote.initials,
                  color: Color(quote.avatarColor),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        quote.providerName,
                        style: body(
                          14.5,
                          weight: FontWeight.w700,
                          color: p.ink,
                        ),
                      ),
                      const SizedBox(height: 2),
                      NStars(
                        rating: quote.rating,
                        reviews: quote.reviews,
                        lang: lang,
                      ),
                    ],
                  ),
                ),
                _roundIcon(context, PhFill.phone, l.callLabel),
                const SizedBox(width: 10),
                _roundIcon(context, PhFill.chatCircleDots, l.messageLabel),
              ],
            ),
          ),
        NCard(
          child: StepList(
            items: [
              StepItem(
                l.stepPaid,
                sub: l.paySecured,
                time: time(TrackStep.paid),
                state: stateOf(TrackStep.paid),
              ),
              StepItem(
                l.stepOnTheWay,
                sub: sharing ? l.stepOnTheWaySub : null,
                time: time(TrackStep.onTheWay),
                state: stateOf(TrackStep.onTheWay),
              ),
              StepItem(
                l.stepOnSite,
                time: time(TrackStep.onSite),
                state: stateOf(TrackStep.onSite),
              ),
              StepItem(
                l.stepWorkDone,
                time: time(TrackStep.workDone),
                state: stateOf(TrackStep.workDone),
              ),
              StepItem(
                l.stepConfirm(name),
                time: time(TrackStep.confirmed),
                state: stateOf(TrackStep.confirmed),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _roundIcon(BuildContext context, IconData icon, String label) =>
      Semantics(
        button: true,
        label: label,
        excludeSemantics: true,
        child: GestureDetector(
          onTap: () => showComingSoon(context, label),
          child: Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: context.palette.soft,
            ),
            child: Icon(icon, size: 19, color: context.palette.softInk),
          ),
        ),
      );
}

/// Le petit plan de la maquette (dessiné, pas une vraie carte : la carte
/// Mapbox viendra avec le suivi en direct).
class _MapPainter extends CustomPainter {
  const _MapPainter({required this.sharing});

  final bool sharing;

  @override
  void paint(Canvas canvas, Size size) {
    // viewBox 350 × 190, « slice » : on couvre toute la surface.
    final scale = [
      size.width / 350,
      size.height / 190,
    ].reduce((a, b) => a > b ? a : b);
    canvas.translate(
      (size.width - 350 * scale) / 2,
      (size.height - 190 * scale) / 2,
    );
    canvas.scale(scale);
    canvas.drawRect(
      const Rect.fromLTWH(0, 0, 350, 190),
      Paint()..color = const Color(0xFFEAF1F8),
    );
    Paint stroke(Color c, double w) => Paint()
      ..color = c
      ..style = PaintingStyle.stroke
      ..strokeWidth = w
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;
    canvas.drawPath(
      Path()
        ..moveTo(-10, 150)
        ..cubicTo(60, 140, 90, 170, 160, 160)
        ..cubicTo(230, 150, 280, 120, 360, 130),
      stroke(const Color(0xFFCFE3F5), 16),
    );
    final big = stroke(Colors.white, 9);
    for (final l in const [
      [-10.0, 40.0, 360.0, 70.0],
      [40.0, -10.0, 70.0, 200.0],
      [150.0, -10.0, 170.0, 200.0],
      [260.0, -10.0, 240.0, 200.0],
      [-10.0, 110.0, 360.0, 100.0],
    ]) {
      canvas.drawLine(Offset(l[0], l[1]), Offset(l[2], l[3]), big);
    }
    final small = stroke(Colors.white, 4)..strokeCap = StrokeCap.butt;
    for (final l in const [
      [100.0, -10.0, 115.0, 200.0],
      [-10.0, 75.0, 360.0, 88.0],
      [205.0, -10.0, 205.0, 200.0],
      [310.0, -10.0, 300.0, 200.0],
    ]) {
      canvas.drawLine(Offset(l[0], l[1]), Offset(l[2], l[3]), small);
    }
    final park = Paint()..color = const Color(0xFFDDEBD6);
    canvas.drawRRect(
      RRect.fromLTRBR(210, 16, 252, 56, const Radius.circular(6)),
      park,
    );
    canvas.drawRRect(
      RRect.fromLTRBR(76, 118, 106, 144, const Radius.circular(6)),
      park,
    );
    // Destination (chez le client).
    canvas.drawCircle(
      const Offset(250, 64),
      12,
      Paint()..color = NexisColors.navy,
    );
    canvas.drawCircle(
      const Offset(250, 64),
      4.5,
      Paint()..color = Colors.white,
    );
    if (!sharing) return;
    canvas.drawPath(
      Path()
        ..moveTo(62, 128)
        ..lineTo(58, 104)
        ..lineTo(160, 98)
        ..lineTo(166, 70)
        ..lineTo(250, 64),
      stroke(NexisColors.brand, 5),
    );
    canvas.drawPath(
      Path()
        ..moveTo(62, 128)
        ..lineTo(58, 104)
        ..lineTo(120, 100),
      stroke(const Color(0xFF9FC2F7), 5),
    );
    canvas.drawCircle(
      const Offset(250, 64),
      12,
      Paint()..color = NexisColors.navy,
    );
    canvas.drawCircle(
      const Offset(250, 64),
      4.5,
      Paint()..color = Colors.white,
    );
    canvas.drawCircle(
      const Offset(120, 100),
      16,
      Paint()..color = NexisColors.brand.withValues(alpha: .15),
    );
    canvas.drawCircle(
      const Offset(120, 100),
      9,
      Paint()..color = NexisColors.brand,
    );
    canvas.drawCircle(const Offset(120, 100), 9, stroke(Colors.white, 3));
  }

  @override
  bool shouldRepaint(_MapPainter oldDelegate) => oldDelegate.sharing != sharing;
}
