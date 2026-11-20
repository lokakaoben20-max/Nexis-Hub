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
import 'mission_card.dart';

typedef _HomeData = ({Profile profile, Wallet wallet, List<Mission> missions});

/// 1. Accueil client, fidèle à la maquette approuvée
/// (design/app-accueil-reference.html) : haut en dégradé ciel, carte qui
/// chevauche une feuille blanche, cinq actions rondes, dernières prestations.
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
    final top = MediaQuery.paddingOf(context).top;
    final width = MediaQuery.sizeOf(context).width;
    final cardScale = (width / 340).clamp(.9, 1.35).toDouble();
    final sheetColor = dark ? p.bg : const Color(0xFFFBFCFE);
    final grey = dark ? p.muted : const Color(0xFF4E5B70);
    final list = data.missions
        .where(
          (m) => _showDone ? m.status == MissionStatus.completed : m.isActive,
        )
        .toList();

    return ColoredBox(
      color: sheetColor,
      child: SingleChildScrollView(
        padding: EdgeInsets.only(bottom: widget.bottomInset + 24),
        child: Stack(
          children: [
            // Ciel : dégradé bleu clair et halo blanc.
            Positioned(
              left: 0,
              right: 0,
              top: 0,
              height: top + 284,
              child: DecoratedBox(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    stops: const [0, .38, .72, 1],
                    colors: dark
                        ? const [
                            Color(0xFF12305E),
                            Color(0xFF0F2547),
                            Color(0xFF0C1B33),
                            Color(0xFF0B1424),
                          ]
                        : const [
                            NexisColors.skyTop,
                            Color(0xFFC9E7FF),
                            Color(0xFFE9F4FF),
                            NexisColors.skyBottom,
                          ],
                  ),
                ),
                child: dark
                    ? null
                    : const Align(
                        alignment: Alignment(-.3, -1.4),
                        child: FractionallySizedBox(
                          widthFactor: 1.1,
                          child: SizedBox(
                            height: 220,
                            child: DecoratedBox(
                              decoration: BoxDecoration(
                                gradient: RadialGradient(
                                  colors: [
                                    Color(0xBFFFFFFF),
                                    Color(0x00FFFFFF),
                                  ],
                                ),
                              ),
                            ),
                          ),
                        ),
                      ),
              ),
            ),
            Padding(
              padding: EdgeInsets.only(top: top + 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _header(context, data, l),
                  Padding(
                    padding: const EdgeInsets.fromLTRB(20, 20, 20, 0),
                    child: Row(
                      children: [
                        Flexible(
                          child: Text(
                            l.hello(data.profile.firstName),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: body(
                              25,
                              weight: FontWeight.w500,
                              color: p.ink,
                            ).copyWith(letterSpacing: -.25),
                          ),
                        ),
                        const SizedBox(width: 10),
                        _chip(l.editProfile, () => widget.onTab(3)),
                      ],
                    ),
                  ),
                  const SizedBox(height: 18),
                  Text(
                    l.myWallets,
                    textAlign: TextAlign.center,
                    style: body(12.5, color: grey),
                  ),
                  const SizedBox(height: 12),
                  // La feuille blanche part du premier tiers de la carte.
                  Stack(
                    clipBehavior: Clip.none,
                    children: [
                      Positioned(
                        left: 0,
                        right: 0,
                        top: 47 * cardScale,
                        bottom: -4000,
                        child: DecoratedBox(
                          decoration: BoxDecoration(
                            color: sheetColor,
                            borderRadius: const BorderRadius.vertical(
                              top: Radius.circular(34),
                            ),
                          ),
                        ),
                      ),
                      Center(child: WalletCard(wallet: data.wallet)),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 20),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _action(
                          PhRegular.toolbox,
                          l.actionServices,
                          widget.onPickService,
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
                      crossAxisAlignment: CrossAxisAlignment.baseline,
                      textBaseline: TextBaseline.alphabetic,
                      children: [
                        Expanded(
                          child: Text(
                            l.lastServices,
                            style: body(
                              15.5,
                              weight: FontWeight.w600,
                              color: p.ink,
                            ),
                          ),
                        ),
                        _tab(
                          l.tabDone,
                          _showDone,
                          () => setState(() => _showDone = true),
                        ),
                        const SizedBox(width: 12),
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
                    height: 132,
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
                            separatorBuilder: (_, _) =>
                                const SizedBox(width: 8),
                            itemBuilder: (context, index) =>
                                _serviceTile(list[index]),
                          ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _header(BuildContext context, _HomeData data, AppLocalizations l) {
    final p = context.palette;
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Row(
        children: [
          Expanded(
            child: Text(
              l.welcomeBack,
              style: body(13, weight: FontWeight.w500, color: p.ink),
            ),
          ),
          Semantics(
            button: true,
            label: 'Notifications',
            excludeSemantics: true,
            child: GestureDetector(
              onTap: () => showComingSoon(context, 'Notifications'),
              child: Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: dark ? p.surface : Colors.white.withValues(alpha: .55),
                ),
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    Icon(PhRegular.bell, size: 21, color: p.ink),
                    const Positioned(
                      right: 12,
                      bottom: 12,
                      child: SizedBox(
                        width: 7,
                        height: 7,
                        child: DecoratedBox(
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: Color(0xFFE5484D),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
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
                width: 44,
                height: 44,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: NexisColors.navy,
                  border: Border.all(color: Colors.white, width: 2),
                ),
                child: Text(
                  data.profile.initials.substring(0, 1),
                  style: body(15, weight: FontWeight.w700, color: Colors.white),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _chip(String label, VoidCallback onTap) {
    final p = context.palette;
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: p.ink.withValues(alpha: .08),
          borderRadius: BorderRadius.circular(99),
        ),
        child: Text(
          label,
          style: body(11.5, weight: FontWeight.w600, color: p.ink),
        ),
      ),
    );
  }

  Widget _action(IconData icon, String label, VoidCallback onTap) {
    final p = context.palette;
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Expanded(
      child: Semantics(
        button: true,
        label: label,
        excludeSemantics: true,
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 2),
            child: Column(
              children: [
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: p.soft,
                    shape: BoxShape.circle,
                  ),
                  child: Icon(icon, color: p.softInk, size: 22),
                ),
                const SizedBox(height: 7),
                Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: body(
                    11,
                    weight: FontWeight.w500,
                    color: dark ? p.muted : const Color(0xFF5B667A),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _tab(String label, bool selected, VoidCallback onTap) {
    final p = context.palette;
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Text(
          label,
          style: body(
            12,
            weight: selected ? FontWeight.w600 : FontWeight.w500,
            color: selected ? p.ink : const Color(0xFF8A94A6),
          ),
        ),
      ),
    );
  }

  Widget _serviceTile(Mission mission) {
    final p = context.palette;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final lang = langOf(context);
    final tileColor = dark ? p.surface : const Color(0xFFEEF1F5);
    return GestureDetector(
      onTap: () => openMission(context, mission),
      child: Container(
        width: 106,
        padding: const EdgeInsets.fromLTRB(8, 12, 8, 10),
        decoration: BoxDecoration(
          color: tileColor,
          borderRadius: BorderRadius.circular(18),
        ),
        child: Column(
          children: [
            Stack(
              clipBehavior: Clip.none,
              children: [
                ServiceBadge(mission.service, size: 50),
                if (mission.rated)
                  Positioned(
                    right: -4,
                    top: -3,
                    child: Container(
                      width: 22,
                      height: 22,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: NexisColors.navy,
                        border: Border.all(color: tileColor, width: 2),
                      ),
                      child: const Icon(
                        PhFill.star,
                        size: 11,
                        color: Colors.white,
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              serviceName(mission.service, lang),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: body(12.5, weight: FontWeight.w600, color: p.ink),
            ),
            const SizedBox(height: 2),
            Text(
              mission.providerName ?? mission.commune,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: body(11, color: dark ? p.muted : const Color(0xFF4E5B70)),
            ),
            const SizedBox(height: 2),
            if (mission.amount != null)
              FittedBox(
                fit: BoxFit.scaleDown,
                child: Text(
                  formatMoney(mission.amount!, lang),
                  style: title(13, color: p.ink),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
