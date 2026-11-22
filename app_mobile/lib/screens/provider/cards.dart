import 'package:flutter/material.dart';

import '../../data/models.dart';
import '../../data/money.dart';
import '../../l10n/app_localizations.dart';
import '../../ui/common.dart';
import '../../ui/icons.dart';
import '../../ui/parts.dart';
import '../../ui/theme.dart';
import 'job.dart';
import 'quote.dart';

void openRequest(BuildContext context, ProviderRequest request) {
  if (request.quoted) return;
  Navigator.of(context).push(
    MaterialPageRoute<void>(
      builder: (_) => SendQuoteScreen(missionId: request.missionId),
    ),
  );
}

void openJob(BuildContext context, ProviderJob job) {
  Navigator.of(context).push(
    MaterialPageRoute<void>(
      builder: (_) => ProviderJobScreen(missionId: job.missionId),
    ),
  );
}

/// Une demande de client (maquette 11) : « Nouveau » et le bouton
/// « Envoyer un devis » les dix premières minutes, l'âge ensuite.
class RequestCard extends StatelessWidget {
  const RequestCard({super.key, required this.request});

  final ProviderRequest request;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    final lang = langOf(context);
    final dark = Theme.of(context).brightness == Brightness.dark;
    final minutes = DateTime.now().difference(request.receivedAt).inMinutes;
    final fresh = minutes < 10 && !request.quoted;
    final Widget pill = request.quoted
        ? Pill(tone: PillTone.ok, icon: PhBold.check, text: l.quoteSentPill)
        : fresh
        ? Container(
            padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
            decoration: BoxDecoration(
              color: dark ? const Color(0xFF16351F) : const Color(0xFFE3F5EA),
              borderRadius: BorderRadius.circular(99),
            ),
            child: Text(
              l.newPill,
              style: body(
                10.5,
                weight: FontWeight.w700,
                color: const Color(0xFF1E8A4C),
              ),
            ),
          )
        : Pill(
            tone: PillTone.wait,
            icon: PhRegular.clock,
            text: _age(l, request.receivedAt),
          );
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: () => openRequest(context, request),
      child: NCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                ServiceBadge(request.service, size: 44),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '${serviceName(request.service, lang)} · ${request.commune}',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: body(
                          14.5,
                          weight: FontWeight.w700,
                          color: p.ink,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        request.summary,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: body(12.5, color: p.muted),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                pill,
              ],
            ),
            if (fresh) ...[
              const SizedBox(height: 10),
              NButton(
                label: l.sendAQuote,
                small: true,
                onPressed: () => openRequest(context, request),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

String _age(AppLocalizations l, DateTime at) {
  final minutes = DateTime.now().difference(at).inMinutes;
  if (minutes < 60) return l.minutesAgo(minutes);
  return l.hoursAgo(minutes ~/ 60);
}

/// Une mission payée, côté prestataire : où elle en est.
class JobCard extends StatelessWidget {
  const JobCard({super.key, required this.job});

  final ProviderJob job;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    final lang = langOf(context);
    final steps = job.steps;
    final String status = steps.containsKey(ProviderStep.finished)
        ? l.jobWaitingClient(job.clientFirstName)
        : steps.containsKey(ProviderStep.arrived)
        ? l.jobOnSite
        : job.arrivalSignaled
        ? l.jobArrivalPending(job.clientFirstName)
        : steps.containsKey(ProviderStep.leftHome)
        ? l.jobOnTheWay
        : l.jobToStart;
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: () => openJob(context, job),
      child: NCard(
        child: Row(
          children: [
            ServiceBadge(job.service, size: 44),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${serviceName(job.service, lang)} · ${job.commune}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: body(14.5, weight: FontWeight.w700, color: p.ink),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    status,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: body(12.5, color: p.muted),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            PaymentPill(
              PaymentState.secured,
              text: formatMoney(job.amount, lang),
            ),
          ],
        ),
      ),
    );
  }
}
