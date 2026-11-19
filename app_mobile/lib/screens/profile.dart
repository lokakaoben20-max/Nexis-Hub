import 'package:flutter/material.dart';

import '../ui/icons.dart';

import '../app_state.dart';
import '../data/models.dart';
import '../l10n/app_localizations.dart';
import '../ui/common.dart';
import '../ui/loader.dart';
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
          padding: const EdgeInsets.fromLTRB(20, 24, 20, 24),
          children: [
            Center(
              child: CircleAvatar(
                radius: 38,
                backgroundColor: const Color(0xFFC2416B),
                child: Text(
                  profile.initials,
                  style: title(22, color: Colors.white),
                ),
              ),
            ),
            const SizedBox(height: 12),
            Center(
              child: Text(
                '${profile.firstName} ${profile.lastName}',
                style: title(20, color: p.ink),
              ),
            ),
            const SizedBox(height: 6),
            Center(
              child: Text(
                l.clientBadge,
                style: body(13, weight: FontWeight.w600, color: p.muted),
              ),
            ),
            const SizedBox(height: 20),
            _group(context, [
              _row(
                context,
                PhFill.phone,
                l.phone,
                value: _phone(profile.phone),
              ),
              _row(context, PhFill.mapPin, l.commune, value: profile.commune),
              _row(
                context,
                PhFill.translate,
                l.language,
                value: _languageName(langOf(context)),
                onTap: () => _pickLanguage(context),
              ),
            ]),
            const SizedBox(height: 12),
            _group(context, [
              _row(
                context,
                PhFill.deviceMobile,
                l.myDevices,
                onTap: () => showComingSoon(context, l.myDevices),
              ),
              _row(
                context,
                PhFill.lifebuoy,
                l.help,
                onTap: () => showComingSoon(context, l.help),
              ),
            ]),
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

  static String _phone(String e164) {
    final m = RegExp(r'^\+243(\d{3})(\d{3})(\d{3})$').firstMatch(e164);
    return m == null ? e164 : '+243 ${m[1]} ${m[2]} ${m[3]}';
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
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: p.line),
      ),
      child: Column(
        children: [
          for (var i = 0; i < rows.length; i++) ...[
            if (i > 0) Divider(height: 1, indent: 64, color: p.line),
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
        padding: const EdgeInsets.all(14),
        child: Row(
          children: [
            // Série B : icône blanche sur carré au dégradé Nexis.
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [NexisColors.halo, NexisColors.gradientEnd],
                ),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(icon, color: Colors.white, size: 18),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    style: body(14.5, weight: FontWeight.w600, color: p.ink),
                  ),
                  if (sub != null) Text(sub, style: body(12.5, color: p.muted)),
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
