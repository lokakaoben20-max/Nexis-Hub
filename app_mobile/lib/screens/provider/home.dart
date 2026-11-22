import 'package:flutter/material.dart';

import '../../app_state.dart';
import '../../data/models.dart';
import '../../data/money.dart';
import '../../l10n/app_localizations.dart';
import '../../ui/common.dart';
import '../../ui/icons.dart';
import '../../ui/loader.dart';
import '../../ui/parts.dart';
import '../../ui/theme.dart';
import 'cards.dart';

/// 11. Accueil prestataire (maquette app-ecrans-v3) : Client / Prestataire,
/// « En service », l'argent disponible et sécurisé, les nouvelles demandes.
class ProviderHomeScreen extends StatefulWidget {
  const ProviderHomeScreen({super.key, required this.onTab});

  final ValueChanged<int> onTab;

  @override
  State<ProviderHomeScreen> createState() => _ProviderHomeScreenState();
}

class _ProviderHomeScreenState extends State<ProviderHomeScreen> {
  bool _saving = false;

  Future<void> _setInService(bool value) async {
    final state = AppScope.of(context);
    setState(() => _saving = true);
    try {
      await state.repository.setInService(value);
      state.dataChanged();
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final repo = AppScope.of(context).repository;
    return SafeArea(
      bottom: false,
      child: Loaded<ProviderHome>(
        load: repo.providerHome,
        builder: (context, home) => _build(context, home),
      ),
    );
  }

  Widget _build(BuildContext context, ProviderHome home) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    final lang = langOf(context);
    final dark = Theme.of(context).brightness == Brightness.dark;
    final requests = home.requests;
    final label = home.available.currency == Currency.cdf ? 'FC' : 'USD';
    return ListView(
      padding: const EdgeInsets.fromLTRB(18, 14, 18, 24),
      children: [
        const SpaceSwitch(),
        const SizedBox(height: 14),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          decoration: BoxDecoration(
            color: p.surface,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: dark ? p.line : const Color(0xFFEEF1F5)),
          ),
          child: Row(
            children: [
              Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: home.inService
                      ? const Color(0xFF1E8A4C)
                      : const Color(0xFFC9D0DB),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      home.inService ? l.inService : l.offService,
                      style: body(14, weight: FontWeight.w700, color: p.ink),
                    ),
                    const SizedBox(height: 1),
                    Text(
                      home.inService
                          ? l.inServiceSub(_communes(home.communes, l))
                          : l.offServiceSub,
                      style: body(12, color: p.muted),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              NToggle(
                value: home.inService,
                label: l.inService,
                onChanged: _saving ? null : _setInService,
              ),
            ],
          ),
        ),
        const SizedBox(height: 14),
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(22),
            gradient: const LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              stops: [0, .45, 1],
              colors: [
                NexisColors.halo,
                NexisColors.gradientStart,
                NexisColors.gradientEnd,
              ],
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '${l.available} · $label',
                style: body(12, color: Colors.white.withValues(alpha: .85)),
              ),
              const SizedBox(height: 4),
              FittedBox(
                fit: BoxFit.scaleDown,
                alignment: Alignment.centerLeft,
                child: Text(
                  formatMoney(home.available, lang),
                  style: title(26, color: Colors.white),
                ),
              ),
              const SizedBox(height: 10),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(PhFill.shieldCheck, size: 15, color: Colors.white),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      l.securedUntilConfirm(formatMoney(home.secured, lang)),
                      style: body(12, color: Colors.white),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 18),
        Row(
          crossAxisAlignment: CrossAxisAlignment.baseline,
          textBaseline: TextBaseline.alphabetic,
          children: [
            Expanded(
              child: Text(
                l.newRequests,
                style: body(15, weight: FontWeight.w600, color: p.ink),
              ),
            ),
            GestureDetector(
              onTap: () => widget.onTab(1),
              child: Text(
                l.seeAll,
                style: body(
                  12.5,
                  weight: FontWeight.w600,
                  color: NexisColors.brand,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        if (!home.inService)
          NInfo(text: l.offServiceHint, icon: PhFill.info)
        else if (requests.isEmpty)
          Padding(
            padding: const EdgeInsets.all(16),
            child: Text(
              l.noRequests,
              textAlign: TextAlign.center,
              style: body(13.5, color: p.muted),
            ),
          )
        else
          for (final request in requests) ...[
            RequestCard(request: request),
            const SizedBox(height: 12),
          ],
        if (home.jobs.isNotEmpty) ...[
          const SizedBox(height: 6),
          Text(
            l.jobsInProgress,
            style: body(15, weight: FontWeight.w600, color: p.ink),
          ),
          const SizedBox(height: 10),
          for (final job in home.jobs) ...[
            JobCard(job: job),
            const SizedBox(height: 12),
          ],
        ],
      ],
    );
  }
}

/// « Limete et Gombe », « Limete, Gombe et Ngaliema ».
String _communes(List<String> communes, AppLocalizations l) {
  if (communes.isEmpty) return '';
  if (communes.length == 1) return communes.first;
  final head = communes.sublist(0, communes.length - 1).join(', ');
  return l.andList(head, communes.last);
}
