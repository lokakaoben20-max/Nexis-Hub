import 'package:flutter/material.dart';

import '../app_state.dart';
import '../data/models.dart';
import '../l10n/app_localizations.dart';
import '../ui/common.dart';
import '../ui/loader.dart';
import '../ui/nx_icon.dart';
import '../ui/nx_parts.dart';
import '../ui/theme.dart';
import '../ui/wallet_panel.dart';
import 'mission_card.dart';

typedef _HomeData = ({Profile profile, Wallet wallet, List<Mission> missions});

String homeGreeting(AppLocalizations l, String name, DateTime time) =>
    time.hour < 12 ? l.helloHome(name) : l.eveningHome(name);

/// 1. Accueil client, d'après la maquette validée le 2026-11-22
/// (design/app-accueil-frontend-design.html) : fond uni, une seule carte de
/// portefeuille, cinq actions en tuiles, puis les prestations (En cours en
/// premier, Terminées ensuite) qui racontent la mission.
class HomeScreen extends StatefulWidget {
  const HomeScreen({
    super.key,
    required this.onTab,
    required this.onPickService,
    this.bottomInset = 0,
  });

  final void Function(int tab) onTab;
  final VoidCallback onPickService;

  /// Hauteur de la barre du bas posée au-dessus de l'écran.
  final double bottomInset;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  /// 0 = En cours, 1 = Terminées.
  int _tab = 0;

  /// Nombre de missions montrées sur l'accueil ; le reste est dans Missions.
  static const _shown = 2;

  @override
  Widget build(BuildContext context) {
    final repo = AppScope.of(context).repository;
    return Loaded<_HomeData>(
      load: () async => (
        profile: await repo.profile(),
        wallet: await repo.wallet(),
        missions: await repo.missions(),
      ),
      builder: _build,
    );
  }

  Widget _build(BuildContext context, _HomeData data) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    final top = MediaQuery.paddingOf(context).top;
    final ongoing = data.missions.where((m) => m.isActive).toList();
    final done = data.missions
        .where((m) => m.status == MissionStatus.completed)
        .toList();
    final list = _tab == 0 ? ongoing : done;

    return ColoredBox(
      color: pageColor(context),
      child: CustomScrollView(
        slivers: [
          SliverPadding(
            padding: EdgeInsets.fromLTRB(18, top + 12, 18, 0),
            sliver: SliverToBoxAdapter(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _header(context, data, l),
                  const SizedBox(height: 16),
                  WalletPanel(wallet: data.wallet),
                  const SizedBox(height: 18),
                  Semantics(
                    container: true,
                    label: l.quickActions,
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _action(
                          'services',
                          l.actionServices,
                          widget.onPickService,
                        ),
                        _action(
                          'deposit',
                          l.actionDeposit,
                          () => showComingSoon(context, l.actionDeposit),
                        ),
                        _action(
                          'withdraw',
                          l.actionWithdraw,
                          () => showComingSoon(context, l.actionWithdraw),
                        ),
                        _action(
                          'history',
                          l.actionHistory,
                          () => widget.onTab(2),
                        ),
                        _action(
                          'more',
                          l.actionMore,
                          () => showComingSoon(context, l.actionMore),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          if (data.missions.isEmpty)
            SliverFillRemaining(
              hasScrollBody: false,
              child: Padding(
                padding: EdgeInsets.fromLTRB(
                  18,
                  12,
                  18,
                  widget.bottomInset + 12,
                ),
                child: _firstRequest(context, l),
              ),
            )
          else
            SliverPadding(
              padding: EdgeInsets.fromLTRB(18, 0, 18, widget.bottomInset + 24),
              sliver: SliverToBoxAdapter(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const SizedBox(height: 22),
                    UnderlineTabs(
                      labels: [l.tabOngoing, l.tabDone],
                      selected: _tab,
                      badges: {0: ongoing.length},
                      onChanged: (i) => setState(() => _tab = i),
                    ),
                    const SizedBox(height: 12),
                    if (list.isEmpty)
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
                      for (final mission in list.take(_shown)) ...[
                        MissionCard(mission: mission, showAction: false),
                        const SizedBox(height: 10),
                      ],
                    if (list.length > _shown)
                      GestureDetector(
                        behavior: HitTestBehavior.opaque,
                        onTap: () => widget.onTab(1),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(vertical: 6),
                          child: Text(
                            l.seeMissions(list.length),
                            textAlign: TextAlign.center,
                            style: body(
                              13.5,
                              weight: FontWeight.w600,
                              color: isDark(context)
                                  ? p.softInk
                                  : NexisColors.brand,
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _firstRequest(BuildContext context, AppLocalizations l) {
    final p = context.palette;
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 340),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              l.firstRequestTitle,
              textAlign: TextAlign.center,
              style: title(17, color: p.ink),
            ),
            const SizedBox(height: 14),
            FilledButton(
              onPressed: widget.onPickService,
              style: FilledButton.styleFrom(
                backgroundColor: NexisColors.brand,
                foregroundColor: Colors.white,
                minimumSize: const Size(0, 48),
                padding: const EdgeInsets.symmetric(
                  horizontal: 22,
                  vertical: 12,
                ),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                ),
              ),
              child: Text(l.requestService, textAlign: TextAlign.center),
            ),
          ],
        ),
      ),
    );
  }

  Widget _header(BuildContext context, _HomeData data, AppLocalizations l) {
    final p = context.palette;
    return Row(
      children: [
        Expanded(
          child: Text(
            homeGreeting(l, data.profile.firstName, DateTime.now()),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: title(21, color: p.ink).copyWith(letterSpacing: -.21),
          ),
        ),
        const SizedBox(width: 10),
        SquareButton(
          label: 'Notifications',
          onTap: () => showComingSoon(context, 'Notifications'),
          child: Stack(
            alignment: Alignment.center,
            clipBehavior: Clip.none,
            children: [
              NxIcon('notification', size: 21, color: p.ink),
              Positioned(
                right: -1,
                top: -1,
                child: Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: const Color(0xFFE5484D),
                    border: Border.all(color: p.surface, width: 2),
                  ),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(width: 10),
        Semantics(
          button: true,
          label: l.navProfile,
          excludeSemantics: true,
          child: GestureDetector(
            onTap: () => widget.onTab(3),
            child: Container(
              width: 42,
              height: 42,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: isDark(context) ? p.surface : NexisColors.navy,
              ),
              child: Text(
                data.profile.initials.substring(0, 1),
                style: body(15, weight: FontWeight.w700, color: Colors.white),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _action(String glyph, String label, VoidCallback onTap) {
    final p = context.palette;
    return Expanded(
      child: Semantics(
        button: true,
        label: label,
        excludeSemantics: true,
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 1),
            child: Column(
              children: [
                Container(
                  width: 52,
                  height: 52,
                  decoration: nxCard(context, radius: 18),
                  alignment: Alignment.center,
                  child: NxIcon(
                    glyph,
                    size: 26,
                    color: isDark(context) ? p.softInk : NexisColors.brand,
                  ),
                ),
                const SizedBox(height: 7),
                Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: body(
                    12,
                    weight: FontWeight.w500,
                    color: mutedColor(context),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
