import 'package:flutter/material.dart';

import '../../app_state.dart';
import '../../data/models.dart';
import '../../data/money.dart';
import '../../l10n/app_localizations.dart';
import '../../ui/common.dart';
import '../../ui/dates.dart';
import '../../ui/icons.dart';
import '../../ui/loader.dart';
import '../../ui/parts.dart';
import '../../ui/theme.dart';
import 'pay.dart';

/// 3. Comparer les devis (maquette app-ecrans-v2) : le mieux noté en avant,
/// sans cacher les autres ; prix et créneau tels que le serveur les donne.
class QuotesScreen extends StatelessWidget {
  const QuotesScreen({super.key, required this.mission});

  final Mission mission;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final lang = langOf(context);
    final repo = AppScope.of(context).repository;
    final place = [
      mission.commune,
      if (mission.detail != null) mission.detail!,
    ].join(', ');
    return Loaded<List<Quote>>(
      load: () => repo.quotes(mission.id),
      builder: (context, quotes) => NScreen(
        children: [
          NTopBar(
            title: l.compareQuotes,
            subtitle:
                '${serviceName(mission.service, lang)} · ${mission.commune}',
          ),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              if (mission.wanted != null)
                Pill(
                  tone: PillTone.wait,
                  icon: PhRegular.calendarBlank,
                  text: mission.wanted!,
                ),
              Pill(tone: PillTone.wait, icon: PhRegular.mapPin, text: place),
            ],
          ),
          for (var i = 0; i < quotes.length; i++)
            _QuoteCard(
              quote: quotes[i],
              best: i == 0 && quotes.length > 1,
              onChoose: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => PayScreen(mission: mission, quote: quotes[i]),
                ),
              ),
            ),
          NInfo(text: l.securedUntilDone),
        ],
      ),
    );
  }
}

class _QuoteCard extends StatelessWidget {
  const _QuoteCard({
    required this.quote,
    required this.best,
    required this.onChoose,
  });

  final Quote quote;
  final bool best;
  final VoidCallback onChoose;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    final lang = langOf(context);
    return Stack(
      clipBehavior: Clip.none,
      children: [
        NCard(
          selected: best,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  NAvatar(
                    initials: quote.initials,
                    color: Color(quote.avatarColor),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          quote.providerName,
                          style: body(
                            14.5,
                            weight: FontWeight.w700,
                            color: p.ink,
                          ),
                        ),
                        const SizedBox(height: 2),
                        NStars(
                          rating: quote.rating,
                          reviews: quote.reviews,
                          lang: lang,
                        ),
                      ],
                    ),
                  ),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(
                        formatMoney(quote.price, lang),
                        style: title(16, color: p.ink),
                      ),
                      Text(
                        formatSlot(quote.slot, lang, capital: true),
                        style: body(11.5, color: p.muted),
                      ),
                    ],
                  ),
                ],
              ),
              const SizedBox(height: 10),
              NButton(
                label: l.chooseProvider(quote.firstName),
                small: true,
                kind: best ? NButtonKind.primary : NButtonKind.ghost,
                onPressed: onChoose,
              ),
            ],
          ),
        ),
        if (best)
          Positioned(
            top: -9,
            left: 14,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
              decoration: BoxDecoration(
                color: NexisColors.brand,
                borderRadius: BorderRadius.circular(99),
              ),
              child: Text(
                l.bestRated,
                style: body(10.5, weight: FontWeight.w700, color: Colors.white),
              ),
            ),
          ),
      ],
    );
  }
}
