import 'package:flutter/material.dart';

import '../../ui/icons.dart';
import '../../ui/theme.dart';

enum StepStatus { done, now, todo }

class StepItem {
  const StepItem(this.title, {this.sub, this.time, required this.state});

  final String title;
  final String? sub;
  final String? time;
  final StepStatus state;
}

/// Frise des étapes (maquette 6) : points bleus pleins pour les étapes
/// faites, point entouré pour l'étape en cours, trait bleu entre les faites.
class StepList extends StatelessWidget {
  const StepList({super.key, required this.items});

  final List<StepItem> items;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final grey = dark ? p.line : const Color(0xFFE3E7EE);
    return Column(
      children: [
        for (var i = 0; i < items.length; i++)
          IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SizedBox(
                  width: 22,
                  child: Column(
                    children: [
                      _dot(items[i].state, p),
                      if (i < items.length - 1)
                        Expanded(
                          child: Container(
                            width: 2,
                            color: items[i].state == StepStatus.done
                                ? NexisColors.brand
                                : grey,
                          ),
                        ),
                    ],
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Padding(
                    padding: EdgeInsets.only(
                      bottom: i < items.length - 1 ? 12 : 0,
                      top: 2,
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          items[i].title,
                          style: body(
                            13.5,
                            weight: items[i].state == StepStatus.todo
                                ? FontWeight.w500
                                : FontWeight.w700,
                            color: items[i].state == StepStatus.todo
                                ? const Color(0xFF8A94A6)
                                : p.ink,
                          ),
                        ),
                        if (items[i].sub != null)
                          Text(items[i].sub!, style: body(12, color: p.muted)),
                      ],
                    ),
                  ),
                ),
                if (items[i].time != null)
                  Padding(
                    padding: const EdgeInsets.only(left: 10, top: 3),
                    child: Text(
                      items[i].time!,
                      style: body(
                        11.5,
                        weight: FontWeight.w500,
                        color: p.muted,
                      ),
                    ),
                  ),
              ],
            ),
          ),
      ],
    );
  }

  Widget _dot(StepStatus state, NexisPalette p) => switch (state) {
    StepStatus.done => Container(
      width: 22,
      height: 22,
      decoration: const BoxDecoration(
        shape: BoxShape.circle,
        color: NexisColors.brand,
      ),
      child: const Icon(PhBold.check, size: 12, color: Colors.white),
    ),
    StepStatus.now => Container(
      width: 22,
      height: 22,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: p.surface,
        border: Border.all(color: NexisColors.brand, width: 2),
        boxShadow: const [BoxShadow(color: Color(0xFFDCEBFF), spreadRadius: 4)],
      ),
      child: const SizedBox(
        width: 8,
        height: 8,
        child: DecoratedBox(
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: NexisColors.brand,
          ),
        ),
      ),
    ),
    StepStatus.todo => Container(
      width: 22,
      height: 22,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: p.surface,
        border: Border.all(color: const Color(0xFFC9D0DB), width: 2),
      ),
    ),
  };
}
