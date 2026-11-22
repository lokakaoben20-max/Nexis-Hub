import 'package:flutter/material.dart';

import '../app_state.dart';
import '../data/models.dart';
import '../l10n/app_localizations.dart';
import '../ui/common.dart';
import '../ui/loader.dart';
import '../ui/nx_icon.dart';
import '../ui/nx_parts.dart';
import '../ui/theme.dart';

/// Retire les accents et la casse pour la recherche (« elec » trouve
/// « Électricité »).
String foldText(String text) {
  const from = 'àâäáãåçéèêëíìîïñóòôöõúùûüýÿœæ';
  const to = 'aaaaaaceeeeiiiinooooouuuuyyoa';
  final lower = text.toLowerCase();
  final out = StringBuffer();
  for (final rune in lower.runes) {
    final ch = String.fromCharCode(rune);
    final i = from.indexOf(ch);
    out.write(i < 0 ? ch : to[i]);
  }
  return out.toString();
}

/// Les sections de « Tous les services » : récents (le plus récent
/// d'abord), nouveaux et recommandés, puis le reste par ordre alphabétique.
/// Qui est « nouveau » ou « recommandé » vient du serveur.
({
  List<CatalogService> recents,
  List<CatalogService> highlights,
  List<CatalogService> others,
})
catalogSections(List<CatalogService> all) {
  final recents = all.where((s) => s.lastRequested != null).toList()
    ..sort((a, b) => b.lastRequested!.compareTo(a.lastRequested!));
  final highlights = all
      .where((s) => s.lastRequested == null && (s.isNew || s.recommended))
      .toList();
  final others =
      all
          .where((s) => s.lastRequested == null && !(s.isNew || s.recommended))
          .toList()
        ..sort((a, b) => foldText(a.name).compareTo(foldText(b.name)));
  return (recents: recents, highlights: highlights, others: others);
}

/// Les services de la feuille « Quel service ? » : les récents d'abord,
/// puis l'ordre du serveur.
List<CatalogService> sheetServices(List<CatalogService> all, {int max = 8}) {
  final recents = all.where((s) => s.lastRequested != null).toList()
    ..sort((a, b) => b.lastRequested!.compareTo(a.lastRequested!));
  final rest = all.where((s) => s.lastRequested == null);
  return [...recents, ...rest].take(max).toList();
}

/// « Tous les services » : récents, nouveaux et recommandés, liste
/// complète, recherche, et la demande libre en bas.
class AllServicesScreen extends StatefulWidget {
  const AllServicesScreen({super.key});

  @override
  State<AllServicesScreen> createState() => _AllServicesScreenState();
}

class _AllServicesScreenState extends State<AllServicesScreen> {
  String _query = '';

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    return Scaffold(
      backgroundColor: pageColor(context),
      body: SafeArea(
        child: Loaded<List<CatalogService>>(
          load: AppScope.of(context).repository.serviceCatalog,
          builder: (context, all) {
            final q = foldText(_query.trim());
            final sections = catalogSections(
              q.isEmpty
                  ? all
                  : all.where((s) => foldText(s.name).contains(q)).toList(),
            );
            final empty =
                sections.recents.isEmpty &&
                sections.highlights.isEmpty &&
                sections.others.isEmpty;
            return ListView(
              padding: const EdgeInsets.fromLTRB(18, 6, 18, 40),
              children: [
                _FullHeader(title: l.allServices),
                const SizedBox(height: 14),
                _SearchField(
                  hint: l.searchService,
                  onChanged: (v) => setState(() => _query = v),
                ),
                if (sections.recents.isNotEmpty)
                  _section(context, l.recents, sections.recents),
                if (sections.highlights.isNotEmpty)
                  _section(context, l.newAndRecommended, sections.highlights),
                if (sections.others.isNotEmpty)
                  _section(context, l.allServices, sections.others),
                if (empty)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 20),
                    child: Text(
                      l.noServiceMatches,
                      textAlign: TextAlign.center,
                      style: body(14, color: mutedColor(context)),
                    ),
                  ),
                const SizedBox(height: 22),
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: p.soft,
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        l.cantFindService,
                        style: body(15, weight: FontWeight.w600, color: p.ink),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        l.cantFindHint,
                        style: body(13.5, color: mutedColor(context)),
                      ),
                      const SizedBox(height: 12),
                      _SolidButton(
                        label: l.describeNeed,
                        onTap: () => Navigator.of(context).push(
                          MaterialPageRoute<void>(
                            builder: (_) => const DescribeNeedScreen(),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  Widget _section(
    BuildContext context,
    String heading,
    List<CatalogService> items,
  ) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    String? sub(CatalogService s) {
      if (s.lastRequested != null) {
        return l.requestedOn(shortDate(context, s.lastRequested!));
      }
      if (s.isNew) return l.addedThisWeek;
      if (s.recommended) return l.recommendedForYou;
      return null;
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(2, 18, 2, 8),
          child: Text(
            heading,
            style: body(
              13,
              weight: FontWeight.w600,
              color: mutedColor(context),
            ),
          ),
        ),
        for (final s in items)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Semantics(
              button: true,
              child: GestureDetector(
                behavior: HitTestBehavior.opaque,
                onTap: () => showComingSoon(context, s.name),
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 10,
                  ),
                  decoration: nxCard(context, radius: 18),
                  child: Row(
                    children: [
                      catalogTile(s),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Flexible(
                                  child: Text(
                                    s.name,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: body(
                                      15,
                                      weight: FontWeight.w600,
                                      color: p.ink,
                                    ),
                                  ),
                                ),
                                if (s.isNew) ...[
                                  const SizedBox(width: 8),
                                  const NewBadge(),
                                ],
                              ],
                            ),
                            if (sub(s) != null)
                              Text(
                                sub(s)!,
                                style: body(12.5, color: mutedColor(context)),
                              ),
                          ],
                        ),
                      ),
                      NxIcon('chevron', size: 16, color: faintColor(context)),
                    ],
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }
}

/// Retour carré et titre d'un écran plein.
class _FullHeader extends StatelessWidget {
  const _FullHeader({required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Row(
      children: [
        SquareButton(
          label: l.back,
          onTap: () => Navigator.of(context).maybePop(),
          child: NxIcon('back', size: 20, color: context.palette.ink),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Text(
            title,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: _title(context),
          ),
        ),
      ],
    );
  }

  TextStyle _title(BuildContext context) =>
      body(20, weight: FontWeight.w600, color: context.palette.ink).copyWith(
        fontFamily: 'Unbounded',
        fontVariations: [const FontVariation.weight(600)],
      );
}

class _SearchField extends StatelessWidget {
  const _SearchField({required this.hint, required this.onChanged});

  final String hint;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Container(
      height: 48,
      padding: const EdgeInsets.symmetric(horizontal: 14),
      decoration: nxCard(context, radius: 16),
      child: Row(
        children: [
          NxIcon('search', size: 20, color: faintColor(context)),
          const SizedBox(width: 10),
          Expanded(
            child: TextField(
              onChanged: onChanged,
              textInputAction: TextInputAction.search,
              style: body(15, weight: FontWeight.w500, color: p.ink),
              cursorColor: NexisColors.brand,
              decoration: InputDecoration(
                hintText: hint,
                hintStyle: body(15, color: faintColor(context)),
                border: InputBorder.none,
                isCollapsed: true,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SolidButton extends StatelessWidget {
  const _SolidButton({required this.label, required this.onTap});

  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          height: 48,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: NexisColors.brand,
            borderRadius: BorderRadius.circular(14),
          ),
          child: Text(
            label,
            style: body(15, weight: FontWeight.w600, color: Colors.white),
          ),
        ),
      ),
    );
  }
}

/// « Décrire mon besoin » : une demande libre, transmise à l'équipe.
/// Le serveur reçoit le titre et le texte ; rien n'est payé à cette étape.
class DescribeNeedScreen extends StatefulWidget {
  const DescribeNeedScreen({super.key});

  @override
  State<DescribeNeedScreen> createState() => _DescribeNeedScreenState();
}

class _DescribeNeedScreenState extends State<DescribeNeedScreen> {
  static const _titleMax = 60;
  static const _textMax = 500;
  final _title = TextEditingController();
  final _text = TextEditingController();
  bool _sending = false;
  bool _sent = false;
  bool _failed = false;
  String _sentTitle = '';
  String _sentText = '';

  @override
  void initState() {
    super.initState();
    _title.addListener(_changed);
    _text.addListener(_changed);
  }

  @override
  void dispose() {
    _title.dispose();
    _text.dispose();
    super.dispose();
  }

  void _changed() => setState(() => _failed = false);

  bool get _ready =>
      _title.text.trim().length > 2 && _text.text.trim().length > 9;

  Future<void> _send() async {
    if (!_ready || _sending) return;
    final title = _title.text.trim();
    final text = _text.text.trim();
    setState(() {
      _sending = true;
      _failed = false;
    });
    try {
      await AppScope.of(context).repository.sendFreeRequest(title, text);
      if (!mounted) return;
      setState(() {
        _sent = true;
        _sentTitle = title;
        _sentText = text;
      });
    } on Object {
      if (mounted) setState(() => _failed = true);
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    return Scaffold(
      backgroundColor: pageColor(context),
      resizeToAvoidBottomInset: true,
      body: SafeArea(
        child: _sent ? _done(context, l, p) : _form(context, l, p),
      ),
    );
  }

  Widget _form(BuildContext context, AppLocalizations l, NexisPalette p) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(18, 6, 18, 40),
      children: [
        _FullHeader(title: l.describeNeed),
        const SizedBox(height: 14),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 2),
          child: Text(
            l.describeLead,
            style: body(14, color: mutedColor(context), height: 1.5),
          ),
        ),
        _label(context, l.describeTypeLabel),
        _field(
          context,
          controller: _title,
          hint: l.describeTypeHint,
          maxLength: _titleMax,
        ),
        _label(context, l.describeTextLabel),
        _field(
          context,
          controller: _text,
          hint: l.describeTextHint,
          maxLength: _textMax,
          lines: 4,
        ),
        Align(
          alignment: Alignment.centerRight,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(4, 6, 4, 0),
            child: Text(
              '${_text.text.length} / $_textMax',
              style: body(12, color: faintColor(context)),
            ),
          ),
        ),
        _label(context, l.photos, optional: l.optional),
        Align(
          alignment: Alignment.centerLeft,
          child: Semantics(
            button: true,
            label: l.addPhoto,
            excludeSemantics: true,
            child: GestureDetector(
              onTap: () => showComingSoon(context, l.addPhoto),
              child: Container(
                width: 84,
                height: 84,
                decoration: BoxDecoration(
                  color: isDark(context) ? p.surface : const Color(0xFFF6F9FF),
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(
                    color: const Color(0xFF9DB6E8),
                    width: 1.5,
                  ),
                ),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    NxIcon('camera', size: 26, color: NexisColors.brand),
                    const SizedBox(height: 4),
                    Text(
                      l.addShort,
                      style: body(
                        12,
                        weight: FontWeight.w600,
                        color: NexisColors.brand,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
        Container(
          margin: const EdgeInsets.only(top: 18, bottom: 14),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          decoration: BoxDecoration(
            color: p.soft,
            borderRadius: BorderRadius.circular(14),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.only(top: 1),
                child: NxIcon(
                  'info',
                  size: 18,
                  color: isDark(context) ? p.softInk : const Color(0xFF0A3D9E),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  l.describeNoPay,
                  style: body(
                    13.5,
                    color: isDark(context)
                        ? p.softInk
                        : const Color(0xFF0A3D9E),
                    height: 1.45,
                  ),
                ),
              ),
            ],
          ),
        ),
        if (_failed)
          Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Text(
              l.requestNotSent,
              style: body(13.5, color: const Color(0xFFB42318)),
            ),
          ),
        _SendButton(
          label: l.sendRequest,
          enabled: _ready && !_sending,
          onTap: _send,
        ),
      ],
    );
  }

  Widget _label(BuildContext context, String text, {String? optional}) {
    final p = context.palette;
    return Padding(
      padding: const EdgeInsets.fromLTRB(2, 16, 2, 8),
      child: Row(
        children: [
          Text(
            text,
            style: body(14, weight: FontWeight.w600, color: p.ink),
          ),
          if (optional != null) ...[
            const SizedBox(width: 6),
            Text(optional, style: body(14, color: faintColor(context))),
          ],
        ],
      ),
    );
  }

  Widget _field(
    BuildContext context, {
    required TextEditingController controller,
    required String hint,
    required int maxLength,
    int lines = 1,
  }) {
    final p = context.palette;
    final ring = isDark(context) ? p.line : const Color(0x1A021937);
    OutlineInputBorder border(Color c, double w) => OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: BorderSide(color: c, width: w),
    );
    return TextField(
      controller: controller,
      maxLength: maxLength,
      maxLines: lines == 1 ? 1 : null,
      minLines: lines,
      textCapitalization: TextCapitalization.sentences,
      style: body(15, weight: FontWeight.w500, color: p.ink, height: 1.4),
      cursorColor: NexisColors.brand,
      buildCounter: (
        _, {
        required currentLength,
        required isFocused,
        maxLength,
      }) => null,
      decoration: InputDecoration(
        hintText: hint,
        hintStyle: body(15, color: faintColor(context)),
        filled: true,
        fillColor: p.surface,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 14,
        ),
        enabledBorder: border(ring, 1),
        focusedBorder: border(NexisColors.brand, 2),
        border: border(ring, 1),
      ),
    );
  }

  Widget _done(BuildContext context, AppLocalizations l, NexisPalette p) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(18, 60, 18, 40),
      children: [
        Center(
          child: Container(
            width: 84,
            height: 84,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: isDark(context)
                  ? const Color(0xFF12301F)
                  : const Color(0xFFE6F4EA),
            ),
            alignment: Alignment.center,
            child: const NxIcon(
              'checkFilled',
              size: 48,
              color: Color(0xFF1E7A3C),
            ),
          ),
        ),
        const SizedBox(height: 18),
        Text(
          l.requestSent,
          textAlign: TextAlign.center,
          style: title(22, color: p.ink),
        ),
        const SizedBox(height: 10),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 6),
          child: Text(
            l.requestSentText,
            textAlign: TextAlign.center,
            style: body(15, color: mutedColor(context), height: 1.5),
          ),
        ),
        const SizedBox(height: 20),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          decoration: nxCard(context, radius: 18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                _sentTitle,
                style: body(15, weight: FontWeight.w600, color: p.ink),
              ),
              const SizedBox(height: 2),
              Text(_sentText, style: body(14, color: mutedColor(context))),
            ],
          ),
        ),
        const SizedBox(height: 22),
        _SendButton(
          label: l.backHome,
          enabled: true,
          onTap: () => Navigator.of(context).popUntil((r) => r.isFirst),
        ),
      ],
    );
  }
}

/// Bouton d'envoi : gris tant que ce n'est pas rempli, puis dégradé Nexis.
class _SendButton extends StatelessWidget {
  const _SendButton({
    required this.label,
    required this.enabled,
    required this.onTap,
  });

  final String label;
  final bool enabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      enabled: enabled,
      child: GestureDetector(
        onTap: enabled ? onTap : null,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          height: 54,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            color: enabled ? null : const Color(0xFFCBD3E1),
            gradient: enabled
                ? const LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [Color(0xFF0870EE), NexisColors.brand],
                  )
                : null,
            boxShadow: enabled
                ? const [
                    BoxShadow(
                      color: Color(0xB30350E6),
                      offset: Offset(0, 10),
                      blurRadius: 24,
                      spreadRadius: -10,
                    ),
                  ]
                : null,
          ),
          child: Text(
            label,
            style: body(16, weight: FontWeight.w600, color: Colors.white),
          ),
        ),
      ),
    );
  }
}
