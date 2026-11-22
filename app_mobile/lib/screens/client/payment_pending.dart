import 'package:flutter/material.dart';

import '../../app_state.dart';
import '../../data/models.dart';
import '../../data/money.dart';
import '../../l10n/app_localizations.dart';
import '../../ui/common.dart';
import '../../ui/dates.dart';
import '../../ui/icons.dart';
import '../../ui/parts.dart';
import '../../ui/theme.dart';
import 'pay.dart';
import 'steps.dart';
import 'tracking.dart';

/// En attente de l'opérateur (maquette lot 1, écran 8, au style du nouvel
/// accueil) : l'app suit l'état réel du paiement ; quand l'opérateur a
/// confirmé, on passe au suivi de la mission.
class PaymentPendingScreen extends StatefulWidget {
  const PaymentPendingScreen({
    super.key,
    required this.mission,
    required this.quote,
    required this.operator,
  });

  final Mission mission;
  final Quote quote;
  final MobileOperator operator;

  @override
  State<PaymentPendingScreen> createState() => _PaymentPendingScreenState();
}

class _PaymentPendingScreenState extends State<PaymentPendingScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _spin = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1400),
  )..repeat();
  final DateTime _sentAt = DateTime.now();
  Object? _error;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _pay());
  }

  Future<void> _pay() async {
    final state = AppScope.of(context);
    try {
      final paid = await state.repository.pay(
        widget.mission.id,
        widget.quote.id,
        widget.operator,
      );
      if (!mounted) return;
      state.dataChanged();
      final navigator = Navigator.of(context);
      navigator.popUntil((route) => route.isFirst);
      navigator.push(
        MaterialPageRoute<void>(
          builder: (_) => TrackingScreen(missionId: paid.id),
        ),
      );
    } catch (error) {
      if (mounted) setState(() => _error = error);
    }
  }

  @override
  void dispose() {
    _spin.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    final lang = langOf(context);
    final op = operatorName(widget.operator);
    final amount = formatMoney(widget.quote.price, lang);
    final reduce = MediaQuery.disableAnimationsOf(context);
    return NScreen(
      bottom: NButton(
        label: l.nothingReceived,
        kind: NButtonKind.ghost,
        onPressed: () => showComingSoon(context, l.nothingReceived),
      ),
      children: [
        NTopBar(title: l.paymentTitle),
        Center(
          child: SizedBox(
            width: 180,
            height: 180,
            child: Stack(
              alignment: Alignment.center,
              children: [
                const DecoratedBox(
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: RadialGradient(
                      colors: [Color(0x380A8CFF), Color(0x000A8CFF)],
                    ),
                  ),
                  child: SizedBox.expand(),
                ),
                Container(
                  margin: const EdgeInsets.all(28),
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: const Color(0x1A0A8CFF),
                    border: Border.all(
                      color: const Color(0x400A8CFF),
                      width: 1.5,
                    ),
                  ),
                ),
                if (!reduce)
                  Padding(
                    padding: const EdgeInsets.all(14),
                    child: RotationTransition(
                      turns: _spin,
                      child: const CustomPaint(
                        size: Size.infinite,
                        painter: _ArcPainter(),
                      ),
                    ),
                  ),
                Container(
                  width: 84,
                  height: 84,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(28),
                    gradient: const LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [NexisColors.halo, NexisColors.gradientEnd],
                    ),
                    boxShadow: const [
                      BoxShadow(
                        color: Color(0x990350E6),
                        offset: Offset(0, 16),
                        blurRadius: 30,
                        spreadRadius: -10,
                      ),
                    ],
                  ),
                  child: const Icon(
                    PhRegular.deviceMobileCamera,
                    size: 38,
                    color: Colors.white,
                  ),
                ),
              ],
            ),
          ),
        ),
        Text(
          l.pendingTitle,
          textAlign: TextAlign.center,
          style: title(21, color: p.ink),
        ),
        Text(
          _error == null ? l.pendingText(op, amount) : '$_error',
          textAlign: TextAlign.center,
          style: body(14, color: p.muted).copyWith(height: 1.5),
        ),
        NCard(
          child: StepList(
            items: [
              StepItem(
                l.pendingSent(op),
                time: formatClock(_sentAt, lang),
                state: StepStatus.done,
              ),
              StepItem(
                l.pendingWaiting,
                sub: l.pendingWithin,
                state: StepStatus.now,
              ),
              StepItem(
                l.pendingSecured,
                sub: l.pendingNotify(widget.quote.firstName),
                state: StepStatus.todo,
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _ArcPainter extends CustomPainter {
  const _ArcPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3
      ..strokeCap = StrokeCap.round;
    paint.color = const Color(0xFF0A8CFF);
    canvas.drawArc(rect.deflate(1.5), -1.57, 1.57, false, paint);
    paint.color = const Color(0x660A8CFF);
    canvas.drawArc(rect.deflate(1.5), 0, 1.57, false, paint);
  }

  @override
  bool shouldRepaint(_ArcPainter oldDelegate) => false;
}
