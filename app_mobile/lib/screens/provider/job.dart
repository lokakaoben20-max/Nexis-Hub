import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

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
import '../client/steps.dart';

/// 13. Mission prestataire (maquette app-ecrans-v3) : le client, l'argent
/// sécurisé, le partage de position au choix, les étapes et un gros
/// bouton pour la suivante.
///
/// L'arrivée suit la règle du serveur : « Je suis arrivé » ne confirme
/// rien seul. Le client confirme sur son téléphone, ou le prestataire tape
/// le code de présence du client (cinq essais au plus).
class ProviderJobScreen extends StatefulWidget {
  const ProviderJobScreen({super.key, required this.missionId});

  final int missionId;

  @override
  State<ProviderJobScreen> createState() => _ProviderJobScreenState();
}

class _ProviderJobScreenState extends State<ProviderJobScreen> {
  final _code = TextEditingController();
  bool _busy = false;
  String? _codeError;

  @override
  void initState() {
    super.initState();
    _code.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _code.dispose();
    super.dispose();
  }

  Future<void> _run(Future<void> Function() action) async {
    final state = AppScope.of(context);
    final messenger = ScaffoldMessenger.of(context);
    final l = AppLocalizations.of(context);
    setState(() => _busy = true);
    try {
      await action();
      state.dataChanged();
    } catch (_) {
      messenger.showSnackBar(SnackBar(content: Text(l.actionFailed)));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _sendCode(ProviderJob job) => _run(() async {
    final l = AppLocalizations.of(context);
    final repo = AppScope.of(context).repository;
    final result = await repo.enterPresenceCode(job.missionId, _code.text);
    final after = await repo.providerJob(job.missionId);
    if (!mounted) return;
    setState(() {
      _code.clear();
      _codeError = switch (result) {
        PresenceResult.confirmed => null,
        PresenceResult.wrongCode => l.wrongCode(after.codeAttemptsLeft),
        PresenceResult.locked => l.codeLocked(job.clientFirstName),
      };
    });
  });

  @override
  Widget build(BuildContext context) {
    final repo = AppScope.of(context).repository;
    return Loaded<ProviderJob>(
      load: () => repo.providerJob(widget.missionId),
      builder: (context, job) => _build(context, job),
    );
  }

  Widget _build(BuildContext context, ProviderJob job) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    final lang = langOf(context);
    final dark = Theme.of(context).brightness == Brightness.dark;
    final repo = AppScope.of(context).repository;
    final name = job.clientFirstName;
    final steps = job.steps;
    final left = steps.containsKey(ProviderStep.leftHome);
    final arrived = steps.containsKey(ProviderStep.arrived);
    final finished = steps.containsKey(ProviderStep.finished);
    final waitingArrival = job.arrivalSignaled && !arrived;
    final current = ProviderStep.values.firstWhere(
      (s) => !steps.containsKey(s),
      orElse: () => ProviderStep.finished,
    );
    StepStatus stateOf(ProviderStep s) => steps.containsKey(s)
        ? StepStatus.done
        : s == current
        ? StepStatus.now
        : StepStatus.todo;
    String? time(ProviderStep s) =>
        steps[s] == null ? null : formatClock(steps[s]!, lang);

    final Widget? primary = finished
        ? null
        : arrived
        ? NButton(
            label: l.btnFinished,
            icon: PhBold.check,
            busy: _busy,
            onPressed: () => _run(() => repo.finishJob(job.missionId)),
          )
        : waitingArrival
        ? null
        : left
        ? NButton(
            label: l.btnArrived,
            icon: PhFill.mapPin,
            busy: _busy,
            onPressed: () => _run(() => repo.signalArrival(job.missionId)),
          )
        : NButton(
            label: l.btnLeave,
            icon: PhFill.navigationArrow,
            busy: _busy,
            onPressed: () => _run(() => repo.leaveForJob(job.missionId)),
          );

    return NScreen(
      bottom: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (primary != null) ...[primary, const SizedBox(height: 10)],
          NButton(
            label: l.callClient(name),
            icon: PhRegular.phone,
            kind: NButtonKind.line,
            onPressed: () => showComingSoon(context, l.callClient(name)),
          ),
        ],
      ),
      children: [
        NTopBar(
          title: l.jobTitle,
          subtitle: '${serviceName(job.service, lang)} · ${job.commune}',
        ),
        NCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  NAvatar(
                    initials: job.clientInitials,
                    color: Color(job.clientColor),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          job.clientName,
                          style: body(
                            14.5,
                            weight: FontWeight.w700,
                            color: p.ink,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          job.place,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: body(12.5, color: p.muted),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  _RoundIcon(
                    icon: PhFill.chatCircleDots,
                    label: l.messageLabel,
                    onTap: () => showComingSoon(context, l.messageLabel),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              PaymentPill(
                PaymentState.secured,
                text: l.securedAmount(formatMoney(job.amount, lang)),
              ),
            ],
          ),
        ),
        if (!finished)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            decoration: BoxDecoration(
              color: p.surface,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: dark ? p.line : const Color(0xFFEEF1F5),
              ),
            ),
            child: Row(
              children: [
                const _RoundIcon(
                  icon: PhFill.navigationArrow,
                  label: '',
                  size: 36,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        l.shareLocation,
                        style: body(14, weight: FontWeight.w700, color: p.ink),
                      ),
                      const SizedBox(height: 1),
                      Text(
                        l.shareLocationSub(name),
                        style: body(12, color: p.muted),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 12),
                NToggle(
                  value: job.sharing,
                  label: l.shareLocation,
                  onChanged: _busy
                      ? null
                      : (v) => _run(() => repo.setSharing(job.missionId, v)),
                ),
              ],
            ),
          ),
        NCard(
          child: StepList(
            items: [
              StepItem(
                l.pStepPaid,
                time: time(ProviderStep.clientPaid),
                state: stateOf(ProviderStep.clientPaid),
              ),
              StepItem(
                l.pStepLeft,
                time: time(ProviderStep.leftHome),
                state: stateOf(ProviderStep.leftHome),
              ),
              StepItem(
                arrived ? l.pStepOnSite : l.pStepArrive,
                sub: arrived
                    ? l.arrivalConfirmed
                    : waitingArrival
                    ? l.arrivalWaitingSub(name)
                    : null,
                time: time(ProviderStep.arrived),
                state: stateOf(ProviderStep.arrived),
              ),
              StepItem(
                l.pStepDone,
                time: time(ProviderStep.finished),
                state: stateOf(ProviderStep.finished),
              ),
            ],
          ),
        ),
        if (waitingArrival) ...[
          NInfo(text: l.arrivalWaiting(name), icon: PhFill.info),
          if (job.codeAttemptsLeft > 0)
            _CodeEntry(
              controller: _code,
              busy: _busy,
              error: _codeError,
              onSubmit: () => _sendCode(job),
            )
          else
            NInfo(
              text: l.codeLocked(name),
              icon: PhFill.lockSimple,
              danger: true,
            ),
        ],
        if (finished)
          NInfo(text: l.finishedNote(name), icon: PhFill.info, violet: true),
      ],
    );
  }
}

class _CodeEntry extends StatelessWidget {
  const _CodeEntry({
    required this.controller,
    required this.busy,
    required this.error,
    required this.onSubmit,
  });

  final TextEditingController controller;
  final bool busy;
  final String? error;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    final ready = controller.text.length == 4 && !busy;
    return NCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            l.presenceCode,
            style: body(13.5, weight: FontWeight.w600, color: p.ink),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: controller,
                  enabled: !busy,
                  keyboardType: TextInputType.number,
                  inputFormatters: [
                    FilteringTextInputFormatter.digitsOnly,
                    LengthLimitingTextInputFormatter(4),
                  ],
                  style: title(20, color: p.ink).copyWith(letterSpacing: 8),
                  decoration: InputDecoration(
                    isDense: true,
                    hintText: '••••',
                    hintStyle: title(20, color: p.muted),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  onSubmitted: (_) => ready ? onSubmit() : null,
                ),
              ),
              const SizedBox(width: 10),
              NButton(
                label: l.confirmCode,
                small: true,
                busy: busy,
                onPressed: ready ? onSubmit : null,
              ),
            ],
          ),
          if (error != null) ...[
            const SizedBox(height: 8),
            Text(
              error!,
              style: body(
                12,
                weight: FontWeight.w600,
                color: NexisColors.danger,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _RoundIcon extends StatelessWidget {
  const _RoundIcon({
    required this.icon,
    required this.label,
    this.onTap,
    this.size = 42,
  });

  final IconData icon;
  final String label;
  final VoidCallback? onTap;
  final double size;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final circle = Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(shape: BoxShape.circle, color: p.soft),
      child: Icon(icon, size: size * .45, color: NexisColors.brand),
    );
    if (onTap == null) return ExcludeSemantics(child: circle);
    return Semantics(
      button: true,
      label: label,
      excludeSemantics: true,
      child: GestureDetector(onTap: onTap, child: circle),
    );
  }
}
