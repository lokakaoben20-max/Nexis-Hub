import 'package:flutter/material.dart';

import '../app_state.dart';
import '../data/models.dart';
import '../l10n/app_localizations.dart';
import '../ui/common.dart';
import '../ui/icons.dart';
import '../ui/loader.dart';
import '../ui/nx_icon.dart';
import '../ui/nx_parts.dart';
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
    final dark = isDark(context);
    return ColoredBox(
      color: pageColor(context),
      child: SafeArea(
        bottom: false,
        child: Loaded<Profile>(
          load: state.repository.profile,
          builder: (context, profile) => ListView(
            padding: const EdgeInsets.fromLTRB(18, 12, 18, 24),
            children: [
              Text(
                l.navProfile,
                style: title(21, color: p.ink).copyWith(letterSpacing: -.21),
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Container(
                    width: 56,
                    height: 56,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: dark ? p.surface : NexisColors.navy,
                    ),
                    child: Text(
                      profile.initials,
                      style: body(
                        18,
                        weight: FontWeight.w700,
                        color: Colors.white,
                      ),
                    ),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${profile.firstName} ${profile.lastName}',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: title(18, color: p.ink),
                        ),
                        Text(
                          _masked(profile.phone),
                          style: body(14, color: mutedColor(context)),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              if (profile.isProvider) ...[
                const SpaceSwitch(),
                const SizedBox(height: 16),
              ],
              _group(context, [
                _row(
                  context,
                  'idCard',
                  l.myInfo,
                  sub: l.myInfoSub,
                  onTap: () => showComingSoon(context, l.myInfo),
                ),
                _row(
                  context,
                  'devices',
                  l.myDevices,
                  sub: l.devicesCount(2),
                  onTap: () => showComingSoon(context, l.myDevices),
                ),
                _row(
                  context,
                  'language',
                  l.language,
                  sub: _languageName(langOf(context)),
                  onTap: () => _pickLanguage(context),
                ),
                _row(
                  context,
                  'bell',
                  l.notifications,
                  sub: l.notificationsSub,
                  onTap: () => showComingSoon(context, l.notifications),
                ),
              ]),
              const SizedBox(height: 14),
              _group(context, [
                _row(
                  context,
                  'headset',
                  l.helpDisputes,
                  sub: l.helpDisputesSub,
                  violet: true,
                  onTap: () => showComingSoon(context, l.helpDisputes),
                ),
                _row(
                  context,
                  'document',
                  l.legalTerms,
                  sub: profile.termsVersion == null
                      ? null
                      : l.termsVersion(
                          longDate(context, profile.termsVersion!),
                        ),
                  onTap: () => showComingSoon(context, l.legalTerms),
                ),
              ]),
              if (!profile.isProvider) ...[
                const SizedBox(height: 14),
                _group(context, [
                  _row(
                    context,
                    'services',
                    l.becomeProvider,
                    sub: l.becomeProviderSub,
                    onTap: () => showComingSoon(context, l.becomeProvider),
                  ),
                ]),
              ],
              const SizedBox(height: 8),
              Semantics(
                button: true,
                child: GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onTap: state.signOut,
                  child: SizedBox(
                    height: 50,
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const NxIcon(
                          'signOut',
                          size: 20,
                          color: Color(0xFFB42318),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          l.signOut,
                          style: body(
                            15,
                            weight: FontWeight.w600,
                            color: const Color(0xFFB42318),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
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
      decoration: nxCard(context),
      clipBehavior: Clip.antiAlias,
      child: Column(
        children: [
          for (var i = 0; i < rows.length; i++) ...[
            if (i > 0) Divider(height: 1, thickness: 1, color: p.line),
            rows[i],
          ],
        ],
      ),
    );
  }

  Widget _row(
    BuildContext context,
    String glyph,
    String label, {
    String? sub,
    bool violet = false,
    VoidCallback? onTap,
  }) {
    final p = context.palette;
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        child: Row(
          children: [
            SoftIconBox(glyph: glyph, violet: violet),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    style: body(15, weight: FontWeight.w600, color: p.ink),
                  ),
                  if (sub != null)
                    Text(sub, style: body(13, color: mutedColor(context))),
                ],
              ),
            ),
            NxIcon('chevron', size: 16, color: faintColor(context)),
          ],
        ),
      ),
    );
  }
}
