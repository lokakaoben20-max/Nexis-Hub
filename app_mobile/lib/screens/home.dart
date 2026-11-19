import 'package:flutter/material.dart';

import '../ui/icons.dart';

import '../app_state.dart';
import '../data/models.dart';
import '../data/money.dart';
import '../l10n/app_localizations.dart';
import '../ui/common.dart';
import '../ui/loader.dart';
import '../ui/theme.dart';
import '../ui/wallet_card.dart';
import 'shell.dart';

typedef _HomeData = ({Profile profile, Wallet wallet, List<Mission> missions});

/// 1. Accueil client (d'après la référence choisie le 2026-11-07).
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key, required this.onTab});

  final void Function(int tab) onTab;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  bool _showDone = true;

  @override
  Widget build(BuildContext context) {
    final repo = AppScope.of(context).repository;
    return Loaded<_HomeData>(
      load: () async => (
        profile: await repo.profile(),
        wallet: await repo.wallet(),
        missions: await repo.missions(),
      ),
      builder: (context, data) => _build(context, data),
    );
  }

  Widget _build(BuildContext context, _HomeData data) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final list = data.missions
        .where(
          (m) => _showDone ? m.status == MissionStatus.completed : m.isActive,
        )
        .toList();
    return DecoratedBox(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          stops: const [0, .42, .42],
          colors: dark
              ? [const Color(0xFF12305E), p.bg, p.bg]
              : [NexisColors.skyTop, NexisColors.skyBottom, p.bg],
        ),
      ),
      child: SafeArea(
        bottom: false,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(0, 12, 0, 24),
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      l.welcomeBack,
                      style: body(13.5, weight: FontWeight.w500, color: p.ink),
                    ),
                  ),
                  IconButton(
                    onPressed: () => showComingSoon(context, 'Notifications'),
                    style: IconButton.styleFrom(backgroundColor: p.surface),
                    icon: Icon(PhRegular.bell, color: p.ink),
                    tooltip: 'Notifications',
                  ),
                  const SizedBox(width: 6),
                  GestureDetector(
                    onTap: () => widget.onTab(3),
                    child: CircleAvatar(
                      radius: 20,
                      backgroundColor: NexisColors.navy,
                      child: Text(
                        data.profile.initials.substring(0, 1),
                        style: title(14, color: Colors.white),
                      ),
                    ),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 6, 20, 0),
              child: Text(
                l.hello(data.profile.firstName),
                style: title(24, color: p.ink),
              ),
            ),
            const SizedBox(height: 14),
            Center(
              child: Text(l.myWallets, style: body(12.5, color: p.muted)),
            ),
            const SizedBox(height: 8),
            WalletCard(wallet: data.wallet),
            const SizedBox(height: 16),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _action(
                    PhRegular.toolbox,
                    l.actionServices,
                    () => showServicePicker(context),
                  ),
                  _action(
                    PhRegular.arrowFatLineDown,
                    l.actionDeposit,
                    () => showComingSoon(context, l.actionDeposit),
                  ),
                  _action(
                    PhRegular.arrowFatLineUp,
                    l.actionWithdraw,
                    () => showComingSoon(context, l.actionWithdraw),
                  ),
                  _action(
                    PhRegular.clockCounterClockwise,
                    l.actionHistory,
                    () => widget.onTab(2),
                  ),
                  _action(
                    PhRegular.slidersHorizontal,
                    l.actionMore,
                    () => showComingSoon(context, l.actionMore),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 22),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Row(
                children: [
                  Expanded(
                    child: Text(l.lastServices, style: title(15, color: p.ink)),
                  ),
                  _tab(
                    l.tabDone,
                    _showDone,
                    () => setState(() => _showDone = true),
                  ),
                  _tab(
                    l.tabOngoing,
                    !_showDone,
                    () => setState(() => _showDone = false),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 10),
            SizedBox(
              height: 150,
              child: list.isEmpty
                  ? Center(
                      child: Text(
                        l.noMissions,
                        style: body(14, color: p.muted),
                      ),
                    )
                  : ListView.separated(
                      scrollDirection: Axis.horizontal,
                      padding: const EdgeInsets.symmetric(horizontal: 20),
                      itemCount: list.length,
                      separatorBuilder: (_, _) => const SizedBox(width: 10),
                      itemBuilder: (context, index) =>
                          _serviceTile(list[index]),
                    ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _action(IconData icon, String label, VoidCallback onTap) {
    final p = context.palette;
    return Expanded(
      child: Semantics(
        button: true,
        label: label,
        excludeSemantics: true,
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(4),
            child: Column(
              children: [
                Container(
                  width: 50,
                  height: 50,
                  decoration: BoxDecoration(
                    color: p.soft,
                    shape: BoxShape.circle,
                  ),
                  child: Icon(icon, color: p.softInk, size: 24),
                ),
                const SizedBox(height: 6),
                Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: body(11.5, weight: FontWeight.w500, color: p.ink),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _tab(String label, bool selected, VoidCallback onTap) => TextButton(
    onPressed: onTap,
    style: TextButton.styleFrom(
      padding: const EdgeInsets.symmetric(horizontal: 8),
      minimumSize: const Size(0, 36),
    ),
    child: Text(
      label,
      style: body(
        13,
        weight: selected ? FontWeight.w700 : FontWeight.w500,
        color: selected ? context.palette.ink : context.palette.muted,
      ),
    ),
  );

  Widget _serviceTile(Mission mission) {
    final p = context.palette;
    final lang = langOf(context);
    return Container(
      width: 120,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: p.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: p.line),
      ),
      child: Column(
        children: [
          ServiceBadge(mission.service, size: 46),
          const SizedBox(height: 8),
          Text(
            serviceName(mission.service, lang),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: body(13, weight: FontWeight.w600, color: p.ink),
          ),
          Text(
            mission.providerName ?? mission.commune,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: body(12, color: p.muted),
          ),
          const Spacer(),
          if (mission.amount != null)
            FittedBox(
              child: Text(
                formatMoney(mission.amount!, lang),
                style: title(13.5, color: p.ink),
              ),
            ),
        ],
      ),
    );
  }
}
