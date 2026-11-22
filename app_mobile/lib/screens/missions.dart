import 'package:flutter/material.dart';

import '../app_state.dart';
import '../data/models.dart';
import '../l10n/app_localizations.dart';
import '../ui/loader.dart';
import '../ui/nx_parts.dart';
import '../ui/theme.dart';
import 'mission_card.dart';

/// 2. Mes missions : en cours (avec leur suite) et terminées, onglets
/// soulignés de la maquette validée.
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
    return ColoredBox(
      color: pageColor(context),
      child: SafeArea(
        bottom: false,
        child: Loaded<List<Mission>>(
          load: AppScope.of(context).repository.missions,
          builder: (context, missions) {
            final ongoing = missions.where((m) => m.isActive).toList();
            final done = missions.where((m) => !m.isActive).toList();
            final shown = _ongoing ? ongoing : done;
            return ListView(
              padding: const EdgeInsets.fromLTRB(18, 12, 18, 24),
              children: [
                Text(
                  l.myMissions,
                  style: title(21, color: p.ink).copyWith(letterSpacing: -.21),
                ),
                const SizedBox(height: 16),
                UnderlineTabs(
                  labels: [l.tabOngoing, l.tabDone],
                  selected: _ongoing ? 0 : 1,
                  badges: {0: ongoing.length},
                  onChanged: (i) => setState(() => _ongoing = i == 0),
                ),
                const SizedBox(height: 12),
                if (shown.isEmpty)
                  Padding(
                    padding: const EdgeInsets.all(24),
                    child: Center(
                      child: Text(
                        l.noMissions,
                        style: body(14, color: p.muted),
                      ),
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
      ),
    );
  }
}
