import 'package:flutter/material.dart';

import '../app_state.dart';
import '../ui/nx_icon.dart';
import '../ui/nx_parts.dart';
import '../ui/loader.dart';
import 'services_list.dart';

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
    final app = AppScope.of(context);
    final provider = app.providerSpace;
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
                  onAllServices: () {
                    _togglePicker();
                    Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => const AllServicesScreen(),
                      ),
                    );
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
                            _item(0, 'home', 'homeFilled', l.navHome),
                            _item(
                              1,
                              'missions',
                              'missionsFilled',
                              l.navMissions,
                            ),
                            const Expanded(child: SizedBox()),
                            _item(2, 'wallet', 'walletFilled', l.navWallet),
                            _item(3, 'profile', 'profileFilled', l.navProfile),
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
                        onClientHome: !provider && _tab == 0,
                        takeHint: app.takeServiceHint,
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

  Widget _item(int index, String glyph, String active, String label) {
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
              NxIcon(selected ? active : glyph, color: shown, size: 25),
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
class _PlusButton extends StatefulWidget {
  const _PlusButton({
    required this.open,
    required this.reduce,
    required this.onClientHome,
    required this.takeHint,
    required this.label,
    required this.ringColor,
    required this.onTap,
  });

  final bool open;
  final bool reduce;
  final bool onClientHome;
  final bool Function() takeHint;
  final String label;
  final Color ringColor;
  final VoidCallback onTap;

  @override
  State<_PlusButton> createState() => _PlusButtonState();
}

class _PlusButtonState extends State<_PlusButton>
    with SingleTickerProviderStateMixin {
  late final _hint = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1550),
  );
  late final _pulse = _hint.drive(
    CurveTween(curve: const Interval(650 / 1550, 1)),
  );
  late final _scale = _pulse.drive(
    TweenSequence<double>([
      TweenSequenceItem(
        tween: Tween(
          begin: 1.0,
          end: 1.18,
        ).chain(CurveTween(curve: Curves.easeOutCubic)),
        weight: 35,
      ),
      TweenSequenceItem(
        tween: Tween(
          begin: 1.18,
          end: 1.0,
        ).chain(CurveTween(curve: Curves.easeInOutCubic)),
        weight: 65,
      ),
    ]),
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _updateHint();
  }

  @override
  void didUpdateWidget(covariant _PlusButton oldWidget) {
    super.didUpdateWidget(oldWidget);
    _updateHint();
  }

  void _updateHint() {
    if (!widget.onClientHome || widget.open) {
      if (_hint.isAnimating) _hint.reset();
      return;
    }
    final firstEntry = widget.takeHint();
    if (widget.reduce) {
      if (_hint.isAnimating) _hint.reset();
    } else if (firstEntry) {
      _hint.forward();
    }
  }

  @override
  void dispose() {
    _hint.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final _PlusButton(:open, :reduce, :label, :ringColor, :onTap) = widget;
    return Semantics(
      button: true,
      label: label,
      excludeSemantics: true,
      child: GestureDetector(
        onTap: onTap,
        child: Stack(
          clipBehavior: Clip.none,
          alignment: Alignment.center,
          children: [
            Positioned.fill(
              child: IgnorePointer(
                child: AnimatedBuilder(
                  animation: _pulse,
                  builder: (context, _) {
                    final progress = _pulse.value;
                    if (progress == 0 || progress == 1) {
                      return const SizedBox.shrink();
                    }
                    final expansion = Curves.easeOutCubic.transform(progress);
                    return Transform.scale(
                      scale: 1.18 + 0.45 * expansion,
                      child: DecoratedBox(
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: NexisColors.brand.withValues(
                              alpha: 0.65 * (1 - progress),
                            ),
                            width: 2.5,
                          ),
                        ),
                      ),
                    );
                  },
                ),
              ),
            ),
            ScaleTransition(
              scale: _scale,
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
                  child: const NxIcon('add', color: Colors.white, size: 26),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// « Quel service ? » (maquette validée) : huit services en tuiles sur trois
/// colonnes, les demandés récemment d'abord, puis « Tous les services », qui ouvre la
/// liste complète. La liste vient du serveur.
class _ServiceSheet extends StatelessWidget {
  const _ServiceSheet({
    required this.open,
    required this.reduce,
    required this.onPicked,
    required this.onAllServices,
  });

  final bool open;
  final bool reduce;
  final void Function(String label) onPicked;
  final VoidCallback onAllServices;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    final dark = isDark(context);
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
            Text(l.whichService, style: title(18, color: p.ink)),
            const SizedBox(height: 4),
            Text(
              l.pickServiceHint,
              style: body(14, color: mutedColor(context)),
            ),
            const SizedBox(height: 14),
            Loaded<List<CatalogService>>(
              load: AppScope.of(context).repository.serviceCatalog,
              builder: (context, all) {
                final shown = sheetServices(all);
                return GridView(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  padding: EdgeInsets.zero,
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 3,
                    mainAxisSpacing: 8,
                    crossAxisSpacing: 8,
                    mainAxisExtent: 88,
                  ),
                  children: [
                    for (final s in shown)
                      _tile(
                        context,
                        label: catalogServiceName(s, langOf(context)),
                        icon: catalogTile(
                          s,
                          size: 44,
                          badge: s.isNew
                              ? NewBadge(ringColor: _tileBg(context))
                              : null,
                        ),
                        onTap: () =>
                            onPicked(catalogServiceName(s, langOf(context))),
                      ),
                    _tile(
                      context,
                      label: l.allServices,
                      icon: ServiceTile(
                        color: const Color(0xFF5B667A),
                        glyph: 'search',
                        size: 44,
                      ),
                      onTap: onAllServices,
                    ),
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  Color _tileBg(BuildContext context) =>
      isDark(context) ? context.palette.bg : const Color(0xFFF3F5F9);

  Widget _tile(
    BuildContext context, {
    required String label,
    required Widget icon,
    required VoidCallback onTap,
  }) {
    final p = context.palette;
    return Semantics(
      button: true,
      label: label,
      excludeSemantics: true,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 6),
          decoration: BoxDecoration(
            color: _tileBg(context),
            borderRadius: BorderRadius.circular(16),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              icon,
              const SizedBox(height: 4),
              Flexible(
                child: Text(
                  label,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  textAlign: TextAlign.center,
                  style: body(
                    12.5,
                    weight: FontWeight.w600,
                    color: p.ink,
                    height: 1.1,
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
