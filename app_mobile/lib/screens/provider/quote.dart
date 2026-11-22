import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

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

/// Lit le prix tapé : des francs entiers, ou des dollars avec au plus deux
/// décimales. Rien de lisible ou zéro : pas de prix.
Money? parsePrice(String text, Currency currency) {
  final clean = text.replaceAll(RegExp(r'\s'), '').replaceAll(',', '.');
  if (clean.isEmpty) return null;
  if (currency == Currency.cdf) {
    if (!RegExp(r'^\d{1,9}$').hasMatch(clean)) return null;
    final value = int.parse(clean);
    return value > 0 ? Money(value, Currency.cdf) : null;
  }
  final match = RegExp(r'^(\d{1,7})(?:\.(\d{1,2}))?$').firstMatch(clean);
  if (match == null) return null;
  final cents =
      int.parse(match.group(1)!) * 100 +
      int.parse((match.group(2) ?? '0').padRight(2, '0'));
  return cents > 0 ? Money(cents, Currency.usd) : null;
}

/// Groupe les francs par milliers pendant la frappe (« 25 000 »).
class _GroupThousands extends TextInputFormatter {
  @override
  TextEditingValue formatEditUpdate(
    TextEditingValue oldValue,
    TextEditingValue newValue,
  ) {
    final digits = newValue.text.replaceAll(RegExp(r'\D'), '');
    final buffer = StringBuffer();
    for (var i = 0; i < digits.length; i++) {
      if (i > 0 && (digits.length - i) % 3 == 0) buffer.write(' ');
      buffer.write(digits[i]);
    }
    final text = buffer.toString();
    return TextEditingValue(
      text: text,
      selection: TextSelection.collapsed(offset: text.length),
    );
  }
}

/// 12. Envoyer un devis (maquette app-ecrans-v3) : la demande avec ses
/// photos, puis le prix et le créneau. Rien d'autre à remplir.
class SendQuoteScreen extends StatefulWidget {
  const SendQuoteScreen({super.key, required this.missionId});

  final int missionId;

  @override
  State<SendQuoteScreen> createState() => _SendQuoteScreenState();
}

class _SendQuoteScreenState extends State<SendQuoteScreen> {
  final _price = TextEditingController();
  final _focus = FocusNode();
  Currency _currency = Currency.cdf;
  DateTime? _slot;
  DateTime? _custom;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _price.addListener(() => setState(() {}));
    _focus.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _price.dispose();
    _focus.dispose();
    super.dispose();
  }

  Future<void> _pickOther() async {
    final now = DateTime.now();
    final day = await showDatePicker(
      context: context,
      firstDate: now,
      lastDate: now.add(const Duration(days: 60)),
      initialDate: _custom ?? now,
    );
    if (day == null || !mounted) return;
    final time = await showTimePicker(
      context: context,
      initialTime: const TimeOfDay(hour: 9, minute: 0),
    );
    if (time == null || !mounted) return;
    final slot = DateTime(day.year, day.month, day.day, time.hour, time.minute);
    if (slot.isBefore(DateTime.now())) return;
    setState(() => _slot = _custom = slot);
  }

  Future<void> _send(Money price) async {
    final state = AppScope.of(context);
    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);
    final l = AppLocalizations.of(context);
    setState(() => _busy = true);
    try {
      await state.repository.sendQuote(widget.missionId, price, _slot!);
      if (!mounted) return;
      state.dataChanged();
      navigator.pop();
      messenger.showSnackBar(SnackBar(content: Text(l.quoteSentToast)));
    } catch (_) {
      if (!mounted) return;
      setState(() => _busy = false);
      messenger.showSnackBar(SnackBar(content: Text(l.quoteFailed)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final repo = AppScope.of(context).repository;
    return Loaded<ProviderRequest>(
      load: () => repo.providerRequest(widget.missionId),
      builder: (context, request) => _build(context, request),
    );
  }

  Widget _build(BuildContext context, ProviderRequest request) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    final lang = langOf(context);
    final dark = Theme.of(context).brightness == Brightness.dark;
    final price = parsePrice(_price.text, _currency);
    final ready = price != null && _slot != null && !request.quoted;
    final slots = [...request.slotChoices, ?_custom];
    return NScreen(
      bottom: NButton(
        label: l.sendTheQuote,
        busy: _busy,
        onPressed: ready ? () => _send(price) : null,
      ),
      children: [
        NTopBar(
          title: l.sendAQuote,
          subtitle:
              '${serviceName(request.service, lang)} · ${request.commune}',
        ),
        NCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                request.description,
                style: body(
                  13,
                  color: dark ? p.ink : const Color(0xFF2A3A52),
                ).copyWith(height: 1.5),
              ),
              if (request.photos > 0) ...[
                const SizedBox(height: 12),
                Row(
                  children: [
                    for (var i = 0; i < request.photos.clamp(0, 3); i++) ...[
                      if (i > 0) const SizedBox(width: 8),
                      _Photo(dark: dark, label: l.photosCount(request.photos)),
                    ],
                  ],
                ),
              ],
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  Pill(
                    tone: PillTone.wait,
                    icon: PhRegular.calendarBlank,
                    text: request.wanted,
                  ),
                  Pill(
                    tone: PillTone.wait,
                    icon: PhRegular.mapPin,
                    text: request.commune,
                  ),
                ],
              ),
            ],
          ),
        ),
        _label(l.yourPrice, p),
        GestureDetector(
          onTap: () => _focus.requestFocus(),
          child: Container(
            padding: const EdgeInsets.fromLTRB(14, 12, 14, 6),
            decoration: BoxDecoration(
              color: p.surface,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: _focus.hasFocus
                    ? NexisColors.brand
                    : (dark ? p.line : const Color(0xFFE3E7EE)),
                width: _focus.hasFocus ? 2 : 1,
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  l.priceAsked,
                  style: body(11.5, weight: FontWeight.w600, color: p.muted),
                ),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _price,
                        focusNode: _focus,
                        enabled: !_busy,
                        keyboardType: TextInputType.numberWithOptions(
                          decimal: _currency == Currency.usd,
                        ),
                        inputFormatters: [
                          FilteringTextInputFormatter.allow(
                            _currency == Currency.usd
                                ? RegExp(r'[0-9.,]')
                                : RegExp(r'[0-9]'),
                          ),
                          LengthLimitingTextInputFormatter(
                            _currency == Currency.cdf ? 11 : 10,
                          ),
                          if (_currency == Currency.cdf) _GroupThousands(),
                        ],
                        style: title(22, color: p.ink),
                        decoration: InputDecoration(
                          isDense: true,
                          border: InputBorder.none,
                          hintText: '0',
                          hintStyle: title(22, color: p.muted),
                        ),
                      ),
                    ),
                    Semantics(
                      button: true,
                      label: l.changeCurrency,
                      child: GestureDetector(
                        onTap: _busy
                            ? null
                            : () => setState(() {
                                _currency = _currency == Currency.cdf
                                    ? Currency.usd
                                    : Currency.cdf;
                                _price.clear();
                              }),
                        child: Padding(
                          padding: const EdgeInsets.all(6),
                          child: Row(
                            children: [
                              Text(
                                _currency == Currency.cdf ? 'FC' : 'USD',
                                style: body(
                                  13,
                                  weight: FontWeight.w600,
                                  color: p.muted,
                                ),
                              ),
                              const SizedBox(width: 2),
                              Icon(
                                PhRegular.caretDown,
                                size: 12,
                                color: p.muted,
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
        _label(l.yourSlot, p),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final slot in slots)
              _Chip(
                label: formatSlot(slot, lang, capital: true),
                selected: _slot == slot,
                onTap: _busy ? null : () => setState(() => _slot = slot),
              ),
            _Chip(
              label: l.otherSlot,
              selected: false,
              onTap: _busy ? null : _pickOther,
            ),
          ],
        ),
      ],
    );
  }

  Widget _label(String text, NexisPalette p) => Padding(
    padding: const EdgeInsets.only(top: 4),
    child: Text(
      text,
      style: body(15, weight: FontWeight.w600, color: p.ink),
    ),
  );
}

class _Chip extends StatelessWidget {
  const _Chip({required this.label, required this.selected, this.onTap});

  final String label;
  final bool selected;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Semantics(
      button: true,
      selected: selected,
      label: label,
      excludeSemantics: true,
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: selected ? p.soft : p.surface,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: selected
                  ? NexisColors.brand
                  : (dark ? p.line : const Color(0xFFE3E7EE)),
              width: selected ? 1.5 : 1,
            ),
          ),
          child: Text(
            label,
            style: body(
              12.5,
              weight: FontWeight.w600,
              color: selected ? NexisColors.brand : p.ink,
            ),
          ),
        ),
      ),
    );
  }
}

/// Case photo de la demande ; les vraies photos arrivent avec le serveur.
class _Photo extends StatelessWidget {
  const _Photo({required this.dark, required this.label});

  final bool dark;
  final String label;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => showComingSoon(context, label),
      child: Container(
        width: 62,
        height: 62,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(14),
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: dark
                ? const [Color(0xFF223047), Color(0xFF1A263A)]
                : const [Color(0xFFDDE6F0), Color(0xFFC8D4E2)],
          ),
        ),
        child: const Icon(PhRegular.image, size: 22, color: Color(0xFF7B8AA0)),
      ),
    );
  }
}
