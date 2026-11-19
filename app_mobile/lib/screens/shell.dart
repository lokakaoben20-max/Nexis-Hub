import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../ui/icons.dart';

import '../data/models.dart';
import '../l10n/app_localizations.dart';
import '../ui/common.dart';
import '../ui/theme.dart';
import 'home.dart';
import 'missions.dart';
import 'profile.dart';
import 'wallet.dart';

/// Barre du bas A : Accueil, Missions, « + » au centre, Portefeuille, Profil.
class Shell extends StatefulWidget {
  const Shell({super.key});

  @override
  State<Shell> createState() => _ShellState();
}

class _ShellState extends State<Shell> {
  int _tab = 0;

  void go(int tab) => setState(() => _tab = tab);

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    final screens = [
      HomeScreen(onTab: go),
      const MissionsScreen(),
      const WalletScreen(),
      const ProfileScreen(),
    ];
    return Scaffold(
      body: IndexedStack(index: _tab, children: screens),
      bottomNavigationBar: DecoratedBox(
        decoration: BoxDecoration(
          color: p.surface,
          border: Border(top: BorderSide(color: p.line)),
        ),
        child: SafeArea(
          top: false,
          child: SizedBox(
            height: 64,
            child: Row(
              children: [
                _item(0, PhRegular.house, PhFill.house, l.navHome),
                _item(
                  1,
                  PhRegular.clipboardText,
                  PhFill.clipboardText,
                  l.navMissions,
                ),
                Expanded(
                  child: Center(child: _PlusButton(label: l.requestService)),
                ),
                _item(2, PhRegular.wallet, PhFill.wallet, l.navWallet),
                _item(3, PhRegular.userCircle, PhFill.userCircle, l.navProfile),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _item(int index, IconData icon, IconData active, String label) {
    final selected = _tab == index;
    final color = selected
        ? Theme.of(context).colorScheme.primary
        : context.palette.muted;
    return Expanded(
      child: Semantics(
        selected: selected,
        button: true,
        label: label,
        excludeSemantics: true,
        child: InkWell(
          onTap: () => go(index),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(selected ? active : icon, color: color, size: 24),
              const SizedBox(height: 3),
              Text(
                label,
                style: body(
                  11,
                  weight: selected ? FontWeight.w600 : FontWeight.w500,
                  color: color,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Le « + » sans texte : il tourne en X et ouvre « Quel service ? ».
class _PlusButton extends StatefulWidget {
  const _PlusButton({required this.label});

  final String label;

  @override
  State<_PlusButton> createState() => _PlusButtonState();
}

class _PlusButtonState extends State<_PlusButton> {
  bool _open = false;

  Future<void> _toggle() async {
    setState(() => _open = true);
    await showServicePicker(context);
    if (mounted) setState(() => _open = false);
  }

  @override
  Widget build(BuildContext context) {
    final reduce = MediaQuery.disableAnimationsOf(context);
    return Semantics(
      button: true,
      label: widget.label,
      excludeSemantics: true,
      child: GestureDetector(
        onTap: _toggle,
        child: AnimatedContainer(
          duration: Duration(milliseconds: reduce ? 0 : 220),
          width: 52,
          height: 52,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: _open
                ? null
                : const LinearGradient(
                    colors: [
                      NexisColors.gradientStart,
                      NexisColors.gradientEnd,
                    ],
                  ),
            color: _open ? NexisColors.navy : null,
            border: Border.all(color: const Color(0xFFDCEBFF), width: 4),
          ),
          child: AnimatedRotation(
            turns: _open ? .125 : 0,
            duration: Duration(milliseconds: reduce ? 0 : 220),
            child: const Icon(PhBold.plus, color: Colors.white, size: 24),
          ),
        ),
      ),
    );
  }
}

Future<void> showServicePicker(BuildContext context) {
  final l = AppLocalizations.of(context);
  final lang = langOf(context);
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: context.palette.surface,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
    ),
    builder: (sheet) {
      final p = sheet.palette;
      final services = Service.values.where((s) => s != Service.autre).toList();
      return SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 22, 20, 12),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(l.whichService, style: title(20, color: p.ink)),
              const SizedBox(height: 16),
              LayoutBuilder(
                builder: (context, box) {
                  final width = (box.maxWidth - 2 * 10) / 3;
                  return Wrap(
                    spacing: 10,
                    runSpacing: 10,
                    children: [
                      for (final service in services)
                        SizedBox(
                          width: width,
                          child: Material(
                            color: p.bg,
                            borderRadius: BorderRadius.circular(16),
                            child: InkWell(
                              borderRadius: BorderRadius.circular(16),
                              onTap: () {
                                Navigator.pop(sheet);
                                showComingSoon(
                                  context,
                                  serviceName(service, lang),
                                );
                              },
                              child: Padding(
                                padding: const EdgeInsets.symmetric(
                                  vertical: 14,
                                  horizontal: 6,
                                ),
                                child: Column(
                                  children: [
                                    ServiceBadge(service, size: 46),
                                    const SizedBox(height: 8),
                                    Text(
                                      serviceName(service, lang),
                                      textAlign: TextAlign.center,
                                      maxLines: 2,
                                      style: body(
                                        12.5,
                                        weight: FontWeight.w600,
                                        color: p.ink,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ),
                        ),
                    ],
                  );
                },
              ),
              const SizedBox(height: 12),
              TextButton.icon(
                onPressed: () {
                  Navigator.pop(sheet);
                  showComingSoon(context, l.notInList);
                },
                icon: const Icon(PhRegular.chatCircleText),
                label: Text(
                  l.notInList,
                  style: body(14, weight: FontWeight.w600),
                ),
              ),
              SizedBox(
                height: math.max(0, MediaQuery.viewInsetsOf(sheet).bottom),
              ),
            ],
          ),
        ),
      );
    },
  );
}
