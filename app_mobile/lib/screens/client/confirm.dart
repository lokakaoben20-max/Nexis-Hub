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
import 'report.dart';

/// 7. Confirmer que c'est fait (maquette app-ecrans-v3) : une question
/// simple, le montant qui sera versé, et « Signaler un problème ».
class ConfirmScreen extends StatefulWidget {
  const ConfirmScreen({super.key, required this.missionId});

  final int missionId;

  @override
  State<ConfirmScreen> createState() => _ConfirmScreenState();
}

class _ConfirmScreenState extends State<ConfirmScreen> {
  bool _busy = false;

  Future<void> _confirm(Mission mission, String name) async {
    final state = AppScope.of(context);
    final messenger = ScaffoldMessenger.of(context);
    final l = AppLocalizations.of(context);
    setState(() => _busy = true);
    try {
      await state.repository.confirmDone(mission.id);
      if (!mounted) return;
      state.dataChanged();
      Navigator.of(context).popUntil((route) => route.isFirst);
      messenger.showSnackBar(SnackBar(content: Text(l.confirmedToast(name))));
    } catch (error) {
      if (!mounted) return;
      setState(() => _busy = false);
      messenger.showSnackBar(SnackBar(content: Text('$error')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final repo = AppScope.of(context).repository;
    return Loaded<Mission>(
      load: () => repo.mission(widget.missionId),
      builder: (context, mission) => _build(context, mission),
    );
  }

  Widget _build(BuildContext context, Mission mission) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    final lang = langOf(context);
    final dark = Theme.of(context).brightness == Brightness.dark;
    final name = mission.chosen?.firstName ?? mission.providerName ?? '';
    final slot = mission.chosen?.slot;
    return NScreen(
      bottom: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          NButton(
            label: l.yesDone,
            icon: PhBold.check,
            busy: _busy,
            onPressed: () => _confirm(mission, name),
          ),
          const SizedBox(height: 10),
          NButton(
            label: l.reportProblem,
            kind: NButtonKind.line,
            onPressed: _busy
                ? null
                : () => Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (_) => ReportScreen(missionId: mission.id),
                    ),
                  ),
          ),
        ],
      ),
      children: [
        NTopBar(title: l.confirmAction),
        Column(
          children: [
            const SizedBox(height: 8),
            Container(
              width: 84,
              height: 84,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: p.soft,
                boxShadow: [
                  BoxShadow(
                    color: dark ? p.surface : const Color(0xFFF1F6FE),
                    spreadRadius: 10,
                  ),
                ],
              ),
              child: ServiceBadge(mission.service, size: 56),
            ),
            const SizedBox(height: 18),
            Text(
              l.confirmQuestion(name),
              textAlign: TextAlign.center,
              style: title(19, color: p.ink).copyWith(height: 1.3),
            ),
            const SizedBox(height: 6),
            Text(
              l.confirmText(name),
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
                      '${serviceName(mission.service, lang)} · ${mission.commune}',
                      style: body(13.5, color: p.muted),
                    ),
                  ),
                  if (slot != null)
                    Text(
                      formatSlot(slot, lang),
                      style: body(13.5, weight: FontWeight.w600, color: p.ink),
                    ),
                ],
              ),
              const SizedBox(height: 9),
              Divider(
                height: 1,
                thickness: 1,
                color: dark ? p.line : const Color(0xFFEEF1F5),
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(
                    child: Text(
                      l.paidTo(name),
                      style: body(15, weight: FontWeight.w700, color: p.ink),
                    ),
                  ),
                  if (mission.amount != null)
                    Text(
                      formatMoney(mission.amount!, lang),
                      style: title(
                        15,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                    ),
                ],
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  const Icon(
                    PhFill.shieldCheck,
                    size: 14,
                    color: NexisColors.brand,
                  ),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      l.amountFixed,
                      style: body(11.5, color: p.muted),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
        NInfo(text: l.report48h, icon: PhFill.info, violet: true),
      ],
    );
  }
}
