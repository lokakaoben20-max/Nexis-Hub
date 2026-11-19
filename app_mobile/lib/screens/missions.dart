import 'package:flutter/material.dart';

import '../app_state.dart';
import '../data/models.dart';
import '../l10n/app_localizations.dart';
import '../ui/loader.dart';
import '../ui/theme.dart';
import 'mission_card.dart';

/// 2. Mes missions : en cours et terminées.
class MissionsScreen extends StatefulWidget {
  const MissionsScreen({super.key});

  @override
  State<MissionsScreen> createState() => _MissionsScreenState();
}

class _MissionsScreenState extends State<MissionsScreen> {
  bool _ongoing = true;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    return SafeArea(
      bottom: false,
      child: Loaded<List<Mission>>(
        load: AppScope.of(context).repository.missions,
        builder: (context, missions) {
          final ongoing = missions.where((m) => m.isActive).toList();
          final done = missions.where((m) => !m.isActive).toList();
          final shown = _ongoing ? ongoing : done;
          return ListView(
            padding: const EdgeInsets.fromLTRB(20, 20, 20, 24),
            children: [
              Text(l.myMissions, style: title(26, color: p.ink)),
              const SizedBox(height: 14),
              SegmentedButton<bool>(
                showSelectedIcon: false,
                segments: [
                  ButtonSegment(
                    value: true,
                    label: Text('${l.tabOngoing} · ${ongoing.length}'),
                  ),
                  ButtonSegment(
                    value: false,
                    label: Text('${l.tabDone} · ${done.length}'),
                  ),
                ],
                selected: {_ongoing},
                onSelectionChanged: (value) =>
                    setState(() => _ongoing = value.first),
              ),
              const SizedBox(height: 14),
              if (shown.isEmpty)
                Padding(
                  padding: const EdgeInsets.all(24),
                  child: Center(
                    child: Text(l.noMissions, style: body(14, color: p.muted)),
                  ),
                )
              else
                for (final mission in shown) ...[
                  MissionCard(mission: mission),
                  const SizedBox(height: 10),
                ],
            ],
          );
        },
      ),
    );
  }
}
