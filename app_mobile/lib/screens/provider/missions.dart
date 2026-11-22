import 'package:flutter/material.dart';

import '../../app_state.dart';
import '../../data/models.dart';
import '../../l10n/app_localizations.dart';
import '../../ui/loader.dart';
import '../../ui/theme.dart';
import 'cards.dart';

/// Missions, côté prestataire : celles en cours, puis les demandes.
class ProviderMissionsScreen extends StatelessWidget {
  const ProviderMissionsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    return SafeArea(
      bottom: false,
      child: Loaded<ProviderHome>(
        load: AppScope.of(context).repository.providerHome,
        builder: (context, home) => ListView(
          padding: const EdgeInsets.fromLTRB(18, 16, 18, 24),
          children: [
            Text(l.myMissions, style: title(22, color: p.ink)),
            const SizedBox(height: 16),
            Text(
              l.jobsInProgress,
              style: body(15, weight: FontWeight.w600, color: p.ink),
            ),
            const SizedBox(height: 10),
            if (home.jobs.isEmpty)
              _empty(l.noMissions, p.muted)
            else
              for (final job in home.jobs) ...[
                JobCard(job: job),
                const SizedBox(height: 12),
              ],
            const SizedBox(height: 6),
            Text(
              l.newRequests,
              style: body(15, weight: FontWeight.w600, color: p.ink),
            ),
            const SizedBox(height: 10),
            if (home.requests.isEmpty)
              _empty(l.noRequests, p.muted)
            else
              for (final request in home.requests) ...[
                RequestCard(request: request),
                const SizedBox(height: 12),
              ],
          ],
        ),
      ),
    );
  }

  Widget _empty(String text, Color color) => Padding(
    padding: const EdgeInsets.all(16),
    child: Text(
      text,
      textAlign: TextAlign.center,
      style: body(13.5, color: color),
    ),
  );
}
