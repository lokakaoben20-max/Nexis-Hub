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
            padding: const EdgeInsets.fromLTRB(18, 16, 18, 24),
            children: [
              Text(l.myMissions, style: title(22, color: p.ink)),
              const SizedBox(height: 14),
              _Segmented(
                labels: ['${l.tabOngoing} · ${ongoing.length}', l.tabDone],
                selected: _ongoing ? 0 : 1,
                onChanged: (i) => setState(() => _ongoing = i == 0),
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
                  const SizedBox(height: 14),
                ],
            ],
          );
        },
      ),
    );
  }
}

/// Sélecteur en pilule de la maquette (fond gris, choix en blanc).
class _Segmented extends StatelessWidget {
  const _Segmented({
    required this.labels,
    required this.selected,
    required this.onChanged,
  });

  final List<String> labels;
  final int selected;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: dark ? p.surface : const Color(0xFFE9EDF3),
        borderRadius: BorderRadius.circular(99),
      ),
      child: Row(
        children: [
          for (var i = 0; i < labels.length; i++)
            Expanded(
              child: Semantics(
                button: true,
                selected: i == selected,
                child: GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onTap: () => onChanged(i),
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 200),
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: i == selected
                          ? (dark ? p.bg : Colors.white)
                          : Colors.transparent,
                      borderRadius: BorderRadius.circular(99),
                      boxShadow: i == selected && !dark
                          ? const [
                              BoxShadow(
                                color: Color(0x14021937),
                                offset: Offset(0, 1),
                                blurRadius: 2,
                              ),
                            ]
                          : null,
                    ),
                    child: Text(
                      labels[i],
                      style: body(
                        13,
                        weight: FontWeight.w600,
                        color: i == selected
                            ? p.ink
                            : (dark ? p.muted : const Color(0xFF5B667A)),
                      ),
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
