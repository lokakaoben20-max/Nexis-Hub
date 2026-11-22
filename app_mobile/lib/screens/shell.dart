import 'package:flutter/material.dart';

import '../app_state.dart';
import '../ui/icons.dart';

import '../data/models.dart';
import '../l10n/app_localizations.dart';
import '../ui/common.dart';
import '../ui/theme.dart';
import 'home.dart';
import 'missions.dart';
import 'profile.dart';
import 'provider/home.dart';
import 'provider/missions.dart';
import 'wallet.dart';

/// Barre du bas de la maquette approuvée (design/app-accueil-reference.html) :
/// Accueil, Missions, « + » surélevé au centre, Portefeuille, Profil.
/// Le « + » tourne en X bleu nuit et ouvre « Quel service ? » au-dessus
/// de la barre ; le X ou le voile referment.
class Shell extends StatefulWidget {
  const Shell({super.key});

  /// Onglet demandé depuis un écran ouvert par-dessus (« Voir mon
  /// portefeuille ») : la barre y bascule dès qu'on revient.
  static final requestedTab = ValueNotifier<int?>(null);

  static const walletTab = 2;

  @override
  State<Shell> createState() => _ShellState();
}

class _ShellState extends State<Shell> {
  int _tab = 0;
  bool _picking = false;
  bool? _shownProvider;

  void go(int tab) => setState(() {
    _tab = tab;
    _picking = false;
  });

  void _onRequestedTab() {
    final tab = Shell.requestedTab.value;
    if (tab == null) return;
    Shell.requestedTab.value = null;
    go(tab);
  }

  @override
  void initState() {
    super.initState();
    Shell.requestedTab.addListener(_onRequestedTab);
  }

  @override
  void dispose() {
    Shell.requestedTab.removeListener(_onRequestedTab);
    super.dispose();
  }

  void _togglePicker() => setState(() => _picking = !_picking);

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final reduce = MediaQuery.disableAnimationsOf(context);
    final safeBottom = MediaQuery.paddingOf(context).bottom;
    // 96 dans la maquette, dont 34 pour la barre d'accueil de l'iPhone.
    final double barHeight = 62 + (safeBottom < 16 ? 16 : safeBottom);
    final provider = AppScope.of(context).providerSpace;
    if (_shownProvider != provider) {
      // Changer d'espace ramène à son accueil.
      _shownProvider = provider;
      _tab = 0;
      _picking = false;
    }
    final screens = [
      provider
          ? ProviderHomeScreen(onTab: go)
          : HomeScreen(
              onTab: go,
              onPickService: _togglePicker,
              bottomInset: barHeight,
            ),
      provider ? const ProviderMissionsScreen() : const MissionsScreen(),
      const WalletScreen(),
      const ProfileScreen(),
    ];
    final barColor = dark ? p.surface : Colors.white;

    return PopScope(
      canPop: !_picking,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop && _picking) _togglePicker();
      },
      child: Scaffold(
        body: Stack(
          children: [
            Positioned.fill(
              // L'accueil passe sous la barre (comme la maquette) ; les
              // autres écrans s'arrêtent au-dessus.
              child: IndexedStack(
                index: _tab,
                children: [
                  for (var i = 0; i < screens.length; i++)
                    i == 0 && !provider
                        ? screens[i]
                        : MediaQuery.removePadding(
                            context: context,
                            removeBottom: true,
                            child: Padding(
                              padding: EdgeInsets.only(bottom: barHeight),
                              child: screens[i],
                            ),
                          ),
                ],
              ),
            ),
            // Voile.
            Positioned.fill(
              child: IgnorePointer(
                ignoring: !_picking,
                child: GestureDetector(
                  onTap: _togglePicker,
                  child: AnimatedOpacity(
                    opacity: _picking ? 1 : 0,
                    duration: Duration(milliseconds: reduce ? 0 : 300),
                    child: const ColoredBox(color: Color(0x59021937)),
                  ),
                ),
              ),
            ),
            // Feuille « Quel service ? », glissée sous le haut arrondi de la barre.
            Positioned(
              left: 0,
              right: 0,
              bottom: barHeight - 10,
              child: IgnorePointer(
                ignoring: !_picking,
                child: _ServiceSheet(
                  open: _picking,
                  reduce: reduce,
                  onPicked: (label) {
                    _togglePicker();
                    showComingSoon(context, label);
                  },
                ),
              ),
            ),
            // Barre du bas, avec le « + » qui dépasse au-dessus.
            Positioned(
              left: 0,
              right: 0,
              bottom: 0,
              height: barHeight + 24,
              child: Stack(
                clipBehavior: Clip.none,
                children: [
                  Positioned(
                    left: 0,
                    right: 0,
                    bottom: 0,
                    height: barHeight,
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        color: barColor,
                        borderRadius: const BorderRadius.vertical(
                          top: Radius.circular(26),
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: dark ? p.line : const Color(0xFFEEF1F5),
                            offset: const Offset(0, -1),
                          ),
                          const BoxShadow(
                            color: Color(0x1F021937),
                            offset: Offset(0, -8),
                            blurRadius: 24,
                            spreadRadius: -12,
                          ),
                        ],
                      ),
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(8, 10, 8, 0),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            _item(0, PhRegular.house, PhFill.house, l.navHome),
                            _item(
                              1,
                              PhRegular.clipboardText,
                              PhFill.clipboardText,
                              l.navMissions,
                            ),
                            const Expanded(child: SizedBox()),
                            _item(
                              2,
                              PhRegular.wallet,
                              PhFill.wallet,
                              l.navWallet,
                            ),
                            _item(
                              3,
                              PhRegular.userCircle,
                              PhFill.userCircle,
                              l.navProfile,
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                  Positioned(
                    top: 0,
                    left: 0,
                    right: 0,
                    child: Center(
                      child: _PlusButton(
                        open: _picking,
                        reduce: reduce,
                        label: _picking ? l.close : l.requestService,
                        ringColor: barColor,
                        onTap: _togglePicker,
                      ),
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

  Widget _item(int index, IconData icon, IconData active, String label) {
    final selected = _tab == index;
    final color = selected ? NexisColors.brand : const Color(0xFF8A94A6);
    final dark = Theme.of(context).brightness == Brightness.dark;
    final shown = selected && dark ? context.palette.softInk : color;
    return Expanded(
      child: Semantics(
        selected: selected,
        button: true,
        label: label,
        excludeSemantics: true,
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: () => go(index),
          child: Column(
            children: [
              Icon(selected ? active : icon, color: shown, size: 23),
              const SizedBox(height: 5),
              Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: body(
                  11,
                  weight: selected ? FontWeight.w600 : FontWeight.w500,
                  color: shown,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Le « + » sans texte : dégradé E, bord blanc, anneau bleu clair.
/// Ouvert : fond bleu nuit, anneau gris, l'icône tourne de 135° (un X).
class _PlusButton extends StatelessWidget {
  const _PlusButton({
    required this.open,
    required this.reduce,
    required this.label,
    required this.ringColor,
    required this.onTap,
  });

  final bool open;
  final bool reduce;
  final String label;
  final Color ringColor;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: label,
      excludeSemantics: true,
      child: GestureDetector(
        onTap: onTap,
        child: AnimatedContainer(
          duration: Duration(milliseconds: reduce ? 0 : 300),
          curve: Curves.ease,
          width: 62,
          height: 62,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            border: Border.all(color: ringColor, width: 5),
            color: open ? NexisColors.navy : null,
            gradient: open
                ? null
                : const LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [NexisColors.halo, NexisColors.gradientEnd],
                  ),
            boxShadow: open
                ? const [
                    BoxShadow(color: Color(0xFFE3E7EE), spreadRadius: 6),
                    BoxShadow(
                      color: Color(0x73021937),
                      offset: Offset(0, 10),
                      blurRadius: 20,
                      spreadRadius: -8,
                    ),
                  ]
                : const [
                    BoxShadow(color: Color(0xFFDCEBFF), spreadRadius: 6),
                    BoxShadow(
                      color: Color(0x800350E6),
                      offset: Offset(0, 10),
                      blurRadius: 20,
                      spreadRadius: -6,
                    ),
                  ],
          ),
          child: AnimatedRotation(
            turns: open ? 135 / 360 : 0,
            duration: Duration(milliseconds: reduce ? 0 : 350),
            curve: const Cubic(.3, 1.4, .5, 1),
            child: const Icon(PhBold.plus, color: Colors.white, size: 26),
          ),
        ),
      ),
    );
  }
}

/// « Quel service ? » : neuf ronds sur trois colonnes, comme la maquette.
/// Le neuvième, « Autre », mène à « Mon besoin n'est pas dans la liste ».
class _ServiceSheet extends StatelessWidget {
  const _ServiceSheet({
    required this.open,
    required this.reduce,
    required this.onPicked,
  });

  final bool open;
  final bool reduce;
  final void Function(String label) onPicked;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final lang = langOf(context);
    final p = context.palette;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final services = Service.values.where((s) => s != Service.autre).toList();
    final tiles = <(Service, String, String)>[
      for (final s in services) (s, serviceName(s, lang), serviceName(s, lang)),
      (Service.autre, l.otherNeed, l.notInList),
    ];
    return AnimatedSlide(
      offset: open ? Offset.zero : const Offset(0, 1.1),
      duration: Duration(milliseconds: reduce ? 0 : 380),
      curve: const Cubic(.2, .9, .3, 1),
      child: Container(
        decoration: BoxDecoration(
          color: dark ? p.surface : Colors.white,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(28)),
        ),
        padding: const EdgeInsets.fromLTRB(18, 20, 18, 44),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(l.whichService, style: title(17, color: p.ink)),
            const SizedBox(height: 4),
            Text(
              l.pickServiceHint,
              style: body(13, color: dark ? p.muted : const Color(0xFF5B667A)),
            ),
            const SizedBox(height: 16),
            GridView.count(
              crossAxisCount: 3,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              padding: EdgeInsets.zero,
              mainAxisSpacing: 16,
              crossAxisSpacing: 6,
              childAspectRatio: 1.3,
              children: [
                for (var i = 0; i < tiles.length; i++)
                  _tile(context, tiles[i], i),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _tile(BuildContext context, (Service, String, String) tile, int i) {
    final (service, label, picked) = tile;
    final visual = serviceVisual(service);
    final p = context.palette;
    final dark = Theme.of(context).brightness == Brightness.dark;
    return AnimatedOpacity(
      opacity: open ? 1 : 0,
      duration: Duration(milliseconds: reduce ? 0 : 250 + 30 * i),
      child: AnimatedSlide(
        offset: open ? Offset.zero : const Offset(0, .12),
        duration: Duration(milliseconds: reduce ? 0 : 250 + 30 * i),
        child: Semantics(
          button: true,
          label: label,
          excludeSemantics: true,
          child: GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTap: () => onPicked(picked),
            child: Column(
              children: [
                Container(
                  width: 56,
                  height: 56,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: dark ? p.bg : Colors.white,
                    border: Border.all(
                      color: dark ? p.line : const Color(0xFFE3E7EE),
                    ),
                  ),
                  child: Icon(visual.icon, size: 28, color: visual.color),
                ),
                const SizedBox(height: 7),
                Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: body(12, weight: FontWeight.w600, color: p.ink),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
