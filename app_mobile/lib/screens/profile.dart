import 'package:flutter/material.dart';

import '../ui/icons.dart';

import '../app_state.dart';
import '../data/models.dart';
import '../l10n/app_localizations.dart';
import '../ui/common.dart';
import '../ui/loader.dart';
import '../ui/parts.dart';
import '../ui/theme.dart';

/// Profil : identité, langue (vraiment changeable), appareils, aide.
class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    final state = AppScope.of(context);
    return SafeArea(
      bottom: false,
      child: Loaded<Profile>(
        load: state.repository.profile,
        builder: (context, profile) => ListView(
          padding: const EdgeInsets.fromLTRB(18, 16, 18, 24),
          children: [
            Text(l.navProfile, style: title(22, color: p.ink)),
            const SizedBox(height: 14),
            Center(
              child: Container(
                width: 74,
                height: 74,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: const Color(0xFFC2416B),
                  border: Border.all(color: p.surface, width: 3),
                  boxShadow: [BoxShadow(color: p.line, spreadRadius: 1)],
                ),
                child: Text(
                  profile.initials,
                  style: title(20, color: Colors.white),
                ),
              ),
            ),
            const SizedBox(height: 12),
            Center(
              child: Text(
                '${profile.firstName} ${profile.lastName}',
                style: title(17, color: p.ink),
              ),
            ),
            const SizedBox(height: 4),
            Center(
              child: Text(
                _masked(profile.phone),
                style: body(12.5, color: p.muted),
              ),
            ),
            const SizedBox(height: 18),
            if (profile.isProvider) ...[
              const SpaceSwitch(),
              const SizedBox(height: 14),
            ],
            _group(context, [
              _row(
                context,
                PhFill.identificationCard,
                l.myInfo,
                sub: l.myInfoSub,
                onTap: () => showComingSoon(context, l.myInfo),
              ),
              _row(
                context,
                PhFill.devices,
                l.myDevices,
                sub: l.devicesCount(2),
                onTap: () => showComingSoon(context, l.myDevices),
              ),
              _row(
                context,
                PhFill.globeHemisphereWest,
                l.language,
                sub: _languageName(langOf(context)),
                onTap: () => _pickLanguage(context),
              ),
              _row(
                context,
                PhFill.headset,
                l.helpDisputes,
                sub: l.helpDisputesSub,
                onTap: () => showComingSoon(context, l.helpDisputes),
              ),
            ]),
            if (!profile.isProvider) ...[
              const SizedBox(height: 12),
              _group(context, [
                _row(
                  context,
                  PhFill.toolbox,
                  l.becomeProvider,
                  sub: l.becomeProviderSub,
                  onTap: () => showComingSoon(context, l.becomeProvider),
                ),
              ]),
            ],
            const SizedBox(height: 18),
            TextButton(
              onPressed: state.signOut,
              child: Text(
                l.signOut,
                style: body(
                  14.5,
                  weight: FontWeight.w600,
                  color: NexisColors.danger,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  static String _masked(String e164) {
    final d = e164.replaceAll(RegExp(r'\D'), '');
    if (d.length < 12) return e164;
    return '+243 ${d.substring(3, 5)} •• •• ${d.substring(d.length - 3)}';
  }

  static String _languageName(String code) =>
      const {'fr': 'Français', 'ln': 'Lingala', 'en': 'English'}[code] ?? code;

  void _pickLanguage(BuildContext context) {
    final state = AppScope.of(context);
    final current = langOf(context);
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: context.palette.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (sheet) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 12),
            for (final code in const ['fr', 'ln', 'en'])
              ListTile(
                title: Text(
                  _languageName(code),
                  style: body(15, weight: FontWeight.w600),
                ),
                trailing: code == current
                    ? const Icon(PhFill.checkCircle, color: NexisColors.brand)
                    : null,
                onTap: () {
                  state.setLocale(Locale(code));
                  Navigator.pop(sheet);
                },
              ),
            const SizedBox(height: 12),
          ],
        ),
      ),
    );
  }

  Widget _group(BuildContext context, List<Widget> rows) {
    final p = context.palette;
    return Container(
      decoration: BoxDecoration(
        color: p.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: Theme.of(context).brightness == Brightness.dark
              ? p.line
              : const Color(0xFFEEF1F5),
        ),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 14),
      child: Column(
        children: [
          for (var i = 0; i < rows.length; i++) ...[
            if (i > 0)
              Divider(
                height: 1,
                thickness: 1,
                color: Theme.of(context).brightness == Brightness.dark
                    ? p.line
                    : const Color(0xFFEEF1F5),
              ),
            rows[i],
          ],
        ],
      ),
    );
  }

  Widget _row(
    BuildContext context,
    IconData icon,
    String label, {
    String? value,
    String? sub,
    VoidCallback? onTap,
  }) {
    final p = context.palette;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(18),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 12),
        child: Row(
          children: [
            // Série B : icône blanche sur carré au dégradé Nexis.
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [NexisColors.halo, NexisColors.gradientEnd],
                ),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, color: Colors.white, size: 20),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    style: body(14.5, weight: FontWeight.w600, color: p.ink),
                  ),
                  if (sub != null) ...[
                    const SizedBox(height: 2),
                    Text(sub, style: body(12, color: p.muted)),
                  ],
                ],
              ),
            ),
            if (value != null) Text(value, style: body(14, color: p.muted)),
            if (onTap != null) ...[
              const SizedBox(width: 6),
              Icon(PhRegular.caretRight, size: 16, color: p.muted),
            ],
          ],
        ),
      ),
    );
  }
}

/// Passage Client / Prestataire (seulement pour qui a les deux rôles).
/// L'espace prestataire de l'app viendra plus tard : on le dit.
