import 'package:flutter/material.dart';

import '../../app_state.dart';
import '../../data/models.dart';
import '../../data/money.dart';
import '../../l10n/app_localizations.dart';
import '../../ui/common.dart';
import '../../ui/icons.dart';
import '../../ui/loader.dart';
import '../../ui/parts.dart';
import '../../ui/theme.dart';
import 'dispute.dart';

String disputeReasonText(AppLocalizations l, DisputeReason reason) =>
    switch (reason) {
      DisputeReason.notFinished => l.reasonNotFinished,
      DisputeReason.badWork => l.reasonBadWork,
      DisputeReason.noShow => l.reasonNoShow,
      DisputeReason.other => l.reasonOther,
    };

/// 25. Signaler un problème (maquette app-ecrans-profil-litige) : une
/// raison, quelques mots, des photos, et l'argent bloqué dit clairement.
class ReportScreen extends StatefulWidget {
  const ReportScreen({super.key, required this.missionId});

  final int missionId;

  @override
  State<ReportScreen> createState() => _ReportScreenState();
}

class _ReportScreenState extends State<ReportScreen> {
  DisputeReason? _reason;
  final _text = TextEditingController();
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _text.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  bool get _ready => _reason != null && _text.text.trim().isNotEmpty;

  Future<void> _send() async {
    final state = AppScope.of(context);
    final messenger = ScaffoldMessenger.of(context);
    final l = AppLocalizations.of(context);
    final navigator = Navigator.of(context);
    setState(() => _busy = true);
    try {
      await state.repository.reportProblem(
        widget.missionId,
        _reason!,
        _text.text,
      );
      if (!mounted) return;
      state.dataChanged();
      navigator.popUntil((route) => route.isFirst);
      navigator.push(
        MaterialPageRoute<void>(
          builder: (_) => DisputeScreen(missionId: widget.missionId),
        ),
      );
    } catch (_) {
      if (!mounted) return;
      setState(() => _busy = false);
      messenger.showSnackBar(SnackBar(content: Text(l.reportFailed)));
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
    return NScreen(
      bottom: NButton(
        label: l.sendReport,
        busy: _busy,
        onPressed: _ready ? _send : null,
      ),
      children: [
        NTopBar(
          title: l.reportProblem,
          subtitle:
              '${serviceName(mission.service, lang)} · ${mission.commune}',
        ),
        Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              l.whatHappened,
              style: body(15, weight: FontWeight.w600, color: p.ink),
            ),
            const SizedBox(height: 10),
            for (final reason in DisputeReason.values) ...[
              _ReasonTile(
                label: disputeReasonText(l, reason),
                selected: _reason == reason,
                onTap: _busy ? null : () => setState(() => _reason = reason),
              ),
              if (reason != DisputeReason.values.last)
                const SizedBox(height: 8),
            ],
          ],
        ),
        Container(
          decoration: BoxDecoration(
            color: p.surface,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: NexisColors.brand, width: 2),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
          child: TextField(
            controller: _text,
            enabled: !_busy,
            minLines: 2,
            maxLines: 5,
            maxLength: 500,
            style: body(13, color: p.ink).copyWith(height: 1.5),
            decoration: InputDecoration(
              border: InputBorder.none,
              counterText: '',
              hintText: l.reportHint,
              hintStyle: body(13, color: p.muted),
            ),
          ),
        ),
        Row(
          children: [
            _PhotoSlot(icon: PhRegular.camera, label: l.addPhoto, dark: dark),
            const SizedBox(width: 8),
            _PhotoSlot(icon: PhRegular.image, label: l.addPhoto, dark: dark),
          ],
        ),
        if (mission.amount != null)
          NInfo(
            text: l.reportFrozen(formatMoney(mission.amount!, lang)),
            icon: PhFill.lockSimple,
            danger: true,
          ),
      ],
    );
  }
}

class _ReasonTile extends StatelessWidget {
  const _ReasonTile({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Semantics(
      selected: selected,
      inMutuallyExclusiveGroup: true,
      button: true,
      label: label,
      excludeSemantics: true,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
          decoration: BoxDecoration(
            color: selected && !dark ? const Color(0xFFFBFDFF) : p.surface,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(
              color: selected
                  ? NexisColors.brand
                  : (dark ? p.line : const Color(0xFFEEF1F5)),
              width: selected ? 2 : 1,
            ),
          ),
          child: Row(
            children: [
              Expanded(
                child: Text(
                  label,
                  style: body(
                    13.5,
                    weight: selected ? FontWeight.w600 : FontWeight.w500,
                    color: p.ink,
                  ),
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

/// Case photo de la maquette. L'envoi des photos arrive avec le serveur
/// des litiges : en attendant, la case le dit au lieu de faire semblant.
class _PhotoSlot extends StatelessWidget {
  const _PhotoSlot({
    required this.icon,
    required this.label,
    required this.dark,
  });

  final IconData icon;
  final String label;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: label,
      excludeSemantics: true,
      child: GestureDetector(
        onTap: () => showComingSoon(context, label),
        child: Container(
          width: 62,
          height: 62,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: dark
                  ? const [Color(0xFF223047), Color(0xFF1A263A)]
                  : const [Color(0xFFDDE6F0), Color(0xFFC8D4E2)],
            ),
          ),
          child: Icon(icon, size: 22, color: const Color(0xFF7B8AA0)),
        ),
      ),
    );
  }
}
