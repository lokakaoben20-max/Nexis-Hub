import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../ui/icons.dart';

import '../app_state.dart';
import '../l10n/app_localizations.dart';
import '../ui/common.dart';
import '../ui/phone.dart';
import '../ui/theme.dart';
import 'signup.dart';
import 'welcome_intro.dart';

/// 15 : bienvenue, piste A retenue (design/bienvenue/bienvenue-pistes.html) :
/// logo et slogan dans le tiers haut, une seule pastille de langue, les
/// métiers en orbite, puis les boutons. Entrée animée d'environ 1,5 s.
class WelcomeScreen extends StatefulWidget {
  const WelcomeScreen({super.key});

  @override
  State<WelcomeScreen> createState() => _WelcomeScreenState();
}

class _WelcomeScreenState extends State<WelcomeScreen>
    with TickerProviderStateMixin {
  late final AnimationController _intro = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1600),
  );
  late final AnimationController _fall = AnimationController(
    vsync: this,
    duration: Duration(
      milliseconds: (VerifiedFan.totalSeconds * 1000).round() + 200,
    ),
  );
  late final AnimationController _breath = AnimationController(
    vsync: this,
    duration: const Duration(seconds: 6),
  );
  late final AnimationController _shine = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1100),
  );
  late final ShineTimer _shineTimer = ShineTimer(_shine);
  bool _started = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_started) return;
    _started = true;
    if (MediaQuery.disableAnimationsOf(context)) {
      _intro.value = 1;
      _fall.value = 1;
      return;
    }
    _intro.forward();
    _fall.forward();
    _breath.repeat(reverse: true);
    _shineTimer.start(
      const Duration(milliseconds: 1550),
      const Duration(seconds: 5),
    );
  }

  @override
  void dispose() {
    _shineTimer.dispose();
    _intro.dispose();
    _fall.dispose();
    _breath.dispose();
    _shine.dispose();
    super.dispose();
  }

  /// Petit menu sous la pastille : les trois langues, la langue en cours
  /// cochée (choix de Ben, 2026-11-20).
  Future<void> _pickLanguage(BuildContext pill) async {
    final state = AppScope.of(context);
    final current = langOf(context);
    final box = pill.findRenderObject()! as RenderBox;
    final overlay =
        Overlay.of(context).context.findRenderObject()! as RenderBox;
    final topLeft = box.localToGlobal(
      Offset(0, box.size.height + 6),
      ancestor: overlay,
    );
    final bottomRight = box.localToGlobal(
      box.size.bottomRight(Offset.zero),
      ancestor: overlay,
    );
    final picked = await showMenu<String>(
      context: context,
      position: RelativeRect.fromRect(
        Rect.fromPoints(topLeft, bottomRight),
        Offset.zero & overlay.size,
      ),
      color: Colors.white,
      elevation: 8,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      items: [
        for (final (code, name) in const [
          ('fr', 'Français'),
          ('ln', 'Lingala'),
          ('en', 'English'),
        ])
          PopupMenuItem<String>(
            value: code,
            height: 44,
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    name,
                    style: body(
                      15,
                      weight: FontWeight.w600,
                      color: NexisColors.navy,
                    ),
                  ),
                ),
                if (code == current)
                  const Icon(PhBold.check, size: 18, color: NexisColors.brand),
              ],
            ),
          ),
      ],
    );
    if (picked != null && picked != current) state.setLocale(Locale(picked));
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final lang = langOf(context);
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light,
      child: Scaffold(
        backgroundColor: NexisColors.brand,
        body: AnimatedBuilder(
          animation: Listenable.merge([_intro, _fall, _breath, _shine]),
          builder: (context, _) {
            final s = _intro.value * 1.6;
            return BreathingBackground(
              breath: _breath.value,
              child: SafeArea(
                child: LayoutBuilder(
                  builder: (context, box) => Padding(
                    padding: const EdgeInsets.fromLTRB(20, 10, 20, 16),
                    child: Column(
                      children: [
                        Align(
                          alignment: Alignment.centerRight,
                          child: IntroFade(
                            seconds: s,
                            start: 1.2,
                            end: 1.6,
                            rise: 0,
                            child: _LanguagePill(
                              code: lang.toUpperCase(),
                              onTap: _pickLanguage,
                            ),
                          ),
                        ),
                        SizedBox(height: box.maxHeight * .06),
                        AssemblingMonogram(seconds: s),
                        const SizedBox(height: 10),
                        SpelledBrand(seconds: s),
                        const SizedBox(height: 22),
                        IntroFade(
                          seconds: s,
                          start: .82,
                          end: 1.27,
                          child: Text(
                            l.slogan,
                            textAlign: TextAlign.center,
                            style: title(21, color: Colors.white, height: 1.28),
                          ),
                        ),
                        const SizedBox(height: 10),
                        IntroFade(
                          seconds: s,
                          start: .95,
                          end: 1.4,
                          child: ConstrainedBox(
                            constraints: const BoxConstraints(maxWidth: 300),
                            child: Text(
                              l.welcomeIntro,
                              textAlign: TextAlign.center,
                              style: body(
                                14.5,
                                color: const Color(0xFFE3F0FF),
                              ).copyWith(height: 1.45),
                            ),
                          ),
                        ),
                        Expanded(
                          child: Center(
                            child: FittedBox(
                              fit: BoxFit.scaleDown,
                              child: Padding(
                                padding: const EdgeInsets.all(8),
                                child: VerifiedFan(
                                  elapsed: _fall.isCompleted
                                      ? 99
                                      : _fall.value *
                                            _fall.duration!.inMilliseconds /
                                            1000,
                                ),
                              ),
                            ),
                          ),
                        ),
                        IntroFade(
                          seconds: s,
                          start: 1.15,
                          end: 1.6,
                          rise: 22,
                          child: Column(
                            children: [
                              ShineSweep(
                                sweep: _shine.value,
                                child: _WhiteButton(
                                  label: l.start,
                                  filled: true,
                                  onTap: () =>
                                      _toNumber(context, fromSignup: true),
                                ),
                              ),
                              const SizedBox(height: 10),
                              _WhiteButton(
                                label: l.haveAccount,
                                filled: false,
                                onTap: () =>
                                    _toNumber(context, fromSignup: false),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            );
          },
        ),
      ),
    );
  }

  void _toNumber(BuildContext context, {required bool fromSignup}) =>
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => NumberScreen(fromSignup: fromSignup),
        ),
      );
}

/// Une seule pastille : la langue en cours ; la toucher ouvre le menu.
class _LanguagePill extends StatelessWidget {
  const _LanguagePill({required this.code, required this.onTap});

  final String code;
  final void Function(BuildContext pill) onTap;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Semantics(
      button: true,
      label: l.language,
      value: code,
      excludeSemantics: true,
      child: Material(
        color: Colors.white.withValues(alpha: .16),
        shape: StadiumBorder(
          side: BorderSide(color: Colors.white.withValues(alpha: .35)),
        ),
        child: InkWell(
          customBorder: const StadiumBorder(),
          onTap: () => onTap(context),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 6),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(PhRegular.globe, size: 14, color: Colors.white),
                const SizedBox(width: 6),
                Text(
                  code,
                  style: body(
                    12.5,
                    weight: FontWeight.w600,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(width: 4),
                const Icon(PhRegular.caretDown, size: 10, color: Colors.white),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _WhiteButton extends StatelessWidget {
  const _WhiteButton({
    required this.label,
    required this.filled,
    required this.onTap,
  });

  final String label;
  final bool filled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      height: 54,
      child: filled
          ? FilledButton(
              onPressed: onTap,
              style: FilledButton.styleFrom(
                backgroundColor: Colors.white,
                foregroundColor: NexisColors.brand,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                ),
              ),
              child: Text(label, style: title(15, color: NexisColors.brand)),
            )
          : OutlinedButton(
              onPressed: onTap,
              style: OutlinedButton.styleFrom(
                side: BorderSide(color: Colors.white.withValues(alpha: .6)),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                ),
              ),
              child: Text(label, style: title(15, color: Colors.white)),
            ),
    );
  }
}

enum _Channel {
  whatsapp('whatsapp', 'WhatsApp'),
  telegram('telegram', 'Telegram'),
  sms('sms', 'SMS');

  const _Channel(this.key, this.label);

  final String key;
  final String label;
}

/// Teintes propres aux écrans de connexion (design/app-connexion-frontend-design.html).
class _Login {
  _Login(this.context);

  final BuildContext context;

  bool get dark => Theme.of(context).brightness == Brightness.dark;
  NexisPalette get p => context.palette;

  Color get ring => dark ? p.line : const Color(0xFFD5DCE8);
  Color get field => p.surface;
  Color get danger => dark ? const Color(0xFFFF8A80) : const Color(0xFFB42318);
  Color get dangerSoft =>
      dark ? const Color(0xFF3A1B1B) : const Color(0xFFFDECEA);
  Color get optionSelected => dark ? p.soft : const Color(0xFFF6F9FF);
  Color get ccBg => dark ? p.bg : const Color(0xFFF8FAFD);
  Color get radio => dark ? p.muted : const Color(0xFF9AA6BA);
  Color get disabled => dark ? p.line : const Color(0xFFCBD3E1);
}

/// Bouton retour des écrans de connexion : carré arrondi de 42 px.
class _LoginBack extends StatelessWidget {
  const _LoginBack();

  @override
  Widget build(BuildContext context) {
    final t = _Login(context);
    return Semantics(
      button: true,
      label: MaterialLocalizations.of(context).backButtonTooltip,
      excludeSemantics: true,
      child: GestureDetector(
        onTap: () => Navigator.maybePop(context),
        child: Container(
          width: 42,
          height: 42,
          decoration: BoxDecoration(
            color: t.p.surface,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(
              color: t.dark ? t.p.line : const Color(0x12021937),
            ),
          ),
          child: Icon(PhRegular.caretLeft, size: 20, color: t.p.ink),
        ),
      ),
    );
  }
}

/// Bouton « Recevoir le code » : gris plat tant qu'il est inactif.
class _LoginButton extends StatelessWidget {
  const _LoginButton({required this.label, required this.onPressed});

  final String label;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    final t = _Login(context);
    final enabled = onPressed != null;
    return Semantics(
      button: true,
      enabled: enabled,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: enabled ? null : t.disabled,
          gradient: enabled
              ? const LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [NexisColors.gradientStart, NexisColors.gradientEnd],
                )
              : null,
          borderRadius: BorderRadius.circular(17),
          boxShadow: enabled
              ? const [
                  BoxShadow(
                    color: Color(0xB30350E6),
                    blurRadius: 24,
                    offset: Offset(0, 10),
                    spreadRadius: -10,
                  ),
                ]
              : null,
        ),
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            borderRadius: BorderRadius.circular(17),
            onTap: onPressed,
            child: SizedBox(
              height: 56,
              width: double.infinity,
              child: Center(
                child: Text(
                  label,
                  style: body(
                    16.5,
                    weight: FontWeight.w600,
                    color: Colors.white,
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Ligne d'erreur sous un champ : icône d'alerte et texte rouge.
class _LoginError extends StatelessWidget {
  const _LoginError(this.text);

  final String? text;

  @override
  Widget build(BuildContext context) {
    final t = _Login(context);
    return Container(
      constraints: const BoxConstraints(minHeight: 20),
      margin: const EdgeInsets.fromLTRB(4, 8, 4, 0),
      child: text == null
          ? null
          : Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Padding(
                  padding: const EdgeInsets.only(top: 1),
                  child: Icon(
                    PhRegular.warningCircle,
                    size: 16,
                    color: t.danger,
                  ),
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(text!, style: body(13.5, color: t.danger)),
                ),
              ],
            ),
    );
  }
}

/// 16 : numéro (+243) et canal du code, d'après la maquette de connexion.
/// Les canaux viennent du serveur (`codeChannels`) : WhatsApp, Telegram, et
/// SMS seulement quand un vrai fournisseur envoie les codes. Pas de logos :
/// trois cartes de choix, comme dans la maquette approuvée.
class NumberScreen extends StatefulWidget {
  const NumberScreen({super.key, required this.fromSignup});

  final bool fromSignup;

  @override
  State<NumberScreen> createState() => _NumberScreenState();
}

class _NumberScreenState extends State<NumberScreen> {
  final _phone = TextEditingController();
  final _focus = FocusNode();
  _Channel? _picked;

  @override
  void initState() {
    super.initState();
    _focus.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _phone.dispose();
    _focus.dispose();
    super.dispose();
  }

  List<_Channel> get _available {
    final keys = AppScope.of(context).repository.codeChannels;
    return [
      for (final c in _Channel.values)
        if (keys.contains(c.key)) c,
    ];
  }

  _Channel? get _channel {
    final available = _available;
    if (available.isEmpty) return null;
    return available.contains(_picked) ? _picked : available.first;
  }

  DrcPhone get _number => DrcPhone.parse(_phone.text);

  void _continue() {
    final number = _number;
    final channel = _channel;
    if (!number.isValid || channel == null) return;
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => CodeScreen(
          phone: number.digits,
          channel: channel.label,
          fromSignup: widget.fromSignup,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final t = _Login(context);
    final p = t.p;
    final number = _number;
    final bad = !number.prefixKnown;
    final channel = _channel;
    final focused = _focus.hasFocus;
    return Scaffold(
      // Le bouton reste collé au-dessus du clavier : le corps se redimensionne.
      resizeToAvoidBottomInset: true,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 6, 20, 0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(
                height: 44,
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: _LoginBack(),
                ),
              ),
              Expanded(
                child: SingleChildScrollView(
                  keyboardDismissBehavior:
                      ScrollViewKeyboardDismissBehavior.onDrag,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const SizedBox(height: 18),
                      Text(
                        widget.fromSignup ? l.yourNumber : l.signInTitle,
                        style: title(25, color: p.ink, height: 1.18),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        l.yourNumberIntro,
                        style: body(15, color: p.muted).copyWith(height: 1.5),
                      ),
                      const SizedBox(height: 20),
                      Container(
                        height: 60,
                        decoration: BoxDecoration(
                          color: t.field,
                          borderRadius: BorderRadius.circular(18),
                          boxShadow: [
                            if (bad) ...[
                              // Le halo d'abord : le trait passe par-dessus.
                              BoxShadow(color: t.dangerSoft, spreadRadius: 6),
                              BoxShadow(color: t.danger, spreadRadius: 2),
                            ] else if (focused) ...[
                              BoxShadow(color: p.soft, spreadRadius: 6),
                              const BoxShadow(
                                color: NexisColors.brand,
                                spreadRadius: 2,
                              ),
                            ] else
                              BoxShadow(color: t.ring, spreadRadius: 1.5),
                          ],
                        ),
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(18),
                          child: Row(
                            children: [
                              Container(
                                height: double.infinity,
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 14,
                                ),
                                alignment: Alignment.center,
                                decoration: BoxDecoration(
                                  color: t.ccBg,
                                  border: Border(
                                    right: BorderSide(color: p.line),
                                  ),
                                ),
                                child: Text(
                                  '+243',
                                  style: body(
                                    17,
                                    weight: FontWeight.w600,
                                    color: p.ink,
                                  ),
                                ),
                              ),
                              Expanded(
                                child: TextField(
                                  controller: _phone,
                                  focusNode: _focus,
                                  autofocus: true,
                                  keyboardType: TextInputType.phone,
                                  textInputAction: TextInputAction.done,
                                  autofillHints: const [
                                    AutofillHints.telephoneNumberNational,
                                  ],
                                  inputFormatters: const [DrcPhoneFormatter()],
                                  onChanged: (_) => setState(() {}),
                                  onSubmitted: (_) => _continue(),
                                  cursorColor: NexisColors.brand,
                                  style:
                                      body(
                                        21,
                                        weight: FontWeight.w600,
                                        color: p.ink,
                                      ).copyWith(
                                        letterSpacing: .42,
                                        fontFeatures: const [
                                          FontFeature.tabularFigures(),
                                        ],
                                      ),
                                  decoration: InputDecoration(
                                    hintText: '81 234 5678',
                                    hintStyle: body(
                                      21,
                                      weight: FontWeight.w500,
                                      color: const Color(0xFFB4BDCC),
                                    ),
                                    border: InputBorder.none,
                                    enabledBorder: InputBorder.none,
                                    focusedBorder: InputBorder.none,
                                    filled: false,
                                    contentPadding: const EdgeInsets.symmetric(
                                      horizontal: 14,
                                    ),
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                      _LoginError(bad ? l.numberNotCongolese : null),
                      const SizedBox(height: 8),
                      Padding(
                        padding: const EdgeInsets.fromLTRB(2, 6, 2, 2),
                        child: Text(
                          l.receiveCodeBy,
                          style: body(
                            14,
                            weight: FontWeight.w600,
                            color: p.ink,
                          ),
                        ),
                      ),
                      const SizedBox(height: 8),
                      if (channel == null)
                        Text(
                          l.noCodeChannel,
                          style: body(13.5, color: t.danger),
                        ),
                      for (final c in _available)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 10),
                          child: _optionCard(
                            c,
                            selected: c == channel,
                            sub: switch (c) {
                              _Channel.whatsapp => l.whatsappSub,
                              _Channel.telegram => l.telegramSub,
                              _Channel.sms => l.smsSub,
                            },
                          ),
                        ),
                    ],
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.only(bottom: 30, top: 12),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Padding(
                          padding: const EdgeInsets.only(top: 1),
                          child: Icon(
                            PhRegular.shieldCheck,
                            size: 18,
                            color: NexisColors.brand,
                          ),
                        ),
                        const SizedBox(width: 9),
                        Expanded(
                          child: Text(
                            l.neverAskCode,
                            style: body(
                              13,
                              color: p.muted,
                            ).copyWith(height: 1.45),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    _LoginButton(
                      label: l.receiveCode,
                      onPressed: number.isValid && channel != null
                          ? _continue
                          : null,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _optionCard(
    _Channel channel, {
    required bool selected,
    required String sub,
  }) {
    final t = _Login(context);
    final p = t.p;
    return Semantics(
      inMutuallyExclusiveGroup: true,
      checked: selected,
      button: true,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: () => setState(() => _picked = channel),
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: selected ? t.optionSelected : t.field,
            borderRadius: BorderRadius.circular(18),
            boxShadow: [
              BoxShadow(
                color: selected ? NexisColors.brand : t.ring,
                spreadRadius: selected ? 2 : 1.5,
              ),
            ],
          ),
          child: Row(
            children: [
              AnimatedContainer(
                duration: const Duration(milliseconds: 150),
                width: 22,
                height: 22,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: selected ? NexisColors.brand : t.radio,
                    width: selected ? 7 : 2,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      channel.label,
                      style: body(15.5, weight: FontWeight.w700, color: p.ink),
                    ),
                    Text(sub, style: body(13, color: p.muted)),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// 17 : le code à 6 chiffres, d'après la maquette de connexion. Le clavier
/// du téléphone sert à le saisir ; le serveur seul décide s'il est bon.
class CodeScreen extends StatefulWidget {
  const CodeScreen({
    super.key,
    required this.phone,
    required this.channel,
    required this.fromSignup,
  });

  final String phone;
  final String channel;
  final bool fromSignup;

  @override
  State<CodeScreen> createState() => _CodeScreenState();
}

class _CodeScreenState extends State<CodeScreen> {
  final _code = TextEditingController();
  final _focus = FocusNode();
  Timer? _timer;
  Timer? _verification;
  late String _channel = widget.channel;
  // Délai avant de pouvoir redemander un code : 60 s (choix de Ben).
  int _left = 60;

  void _restart() {
    _timer?.cancel();
    setState(() => _left = 60);
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!mounted) return;
      setState(() => _left = _left > 0 ? _left - 1 : 0);
      if (_left == 0) timer.cancel();
    });
  }

  void _toast(String text) {
    final t = _Login(context);
    ScaffoldMessenger.of(context)
      ..clearSnackBars()
      ..showSnackBar(
        SnackBar(
          content: Text(text, style: body(14, color: Colors.white)),
          backgroundColor: NexisColors.navy,
          behavior: SnackBarBehavior.floating,
          margin: const EdgeInsets.fromLTRB(20, 0, 20, 20),
          duration: const Duration(milliseconds: 2200),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
            side: t.dark ? BorderSide(color: t.p.line) : BorderSide.none,
          ),
        ),
      );
  }

  void _switchTo(_Channel channel) {
    _code.clear();
    setState(() => _channel = channel.label);
    _restart();
    _toast(AppLocalizations.of(context).codeSentToast(channel.label));
  }

  void _resend() {
    if (_left > 0) return;
    _code.clear();
    _restart();
    _toast(AppLocalizations.of(context).codeResentToast(_channel));
  }

  @override
  void initState() {
    super.initState();
    _restart();
    _code.addListener(() {
      setState(() {});
      _verification?.cancel();
      if (_code.text.length == 6) {
        // Aperçu : code simulé. La vraie vérification appartient au serveur.
        _verification = Timer(const Duration(milliseconds: 250), _afterCode);
      }
    });
  }

  Future<void> _afterCode() async {
    if (!mounted || ModalRoute.of(context)?.isCurrent != true) return;
    final navigator = Navigator.of(context);
    final state = AppScope.of(context);
    final phone = '+243${widget.phone}';
    if (!state.repository.openDemoAccount(phone)) {
      _timer?.cancel();
      if (!widget.fromSignup) {
        final l = AppLocalizations.of(context);
        final wantsSignup = await showDialog<bool>(
          context: context,
          builder: (dialogContext) => AlertDialog(
            title: Text(l.noAccountTitle),
            content: Text(l.noAccountHint),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(dialogContext).pop(false),
                child: Text(l.changeLoginNumber),
              ),
              FilledButton(
                onPressed: () => Navigator.of(dialogContext).pop(true),
                child: Text(l.signupCreateProfile),
              ),
            ],
          ),
        );
        if (!mounted) return;
        if (wantsSignup != true) {
          navigator.pop();
          return;
        }
      }
      final created = await navigator.push<bool>(
        MaterialPageRoute(builder: (_) => SignupScreen(phone: phone)),
      );
      if (!mounted) return;
      if (created != true) {
        _code.clear();
        _restart();
        return;
      }
    }
    navigator.popUntil((route) => route.isFirst);
    state.signIn();
  }

  @override
  void dispose() {
    _timer?.cancel();
    _verification?.cancel();
    _code.dispose();
    _focus.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final t = _Login(context);
    final p = t.p;
    final digits = widget.phone.replaceAll(RegExp(r'\D'), '');
    final masked =
        '+243 ${digits.substring(0, 2)} •• •• ${digits.substring(digits.length - 3)}';
    final keys = AppScope.of(context).repository.codeChannels;
    final others = [
      for (final c in _Channel.values)
        if (c.label != _channel && keys.contains(c.key)) c,
    ];
    return Scaffold(
      resizeToAvoidBottomInset: true,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 6, 20, 0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(
                height: 44,
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: _LoginBack(),
                ),
              ),
              Expanded(
                child: SingleChildScrollView(
                  keyboardDismissBehavior:
                      ScrollViewKeyboardDismissBehavior.onDrag,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const SizedBox(height: 18),
                      Text(
                        l.enterCode,
                        style: title(25, color: p.ink, height: 1.18),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        _channel == 'SMS'
                            ? l.codeSentBySms(masked)
                            : l.codeSentTo(_channel, masked),
                        style: body(15, color: p.muted).copyWith(height: 1.5),
                      ),
                      const SizedBox(height: 24),
                      // Le vrai champ couvre les six cases, invisible : toucher
                      // une case ouvre le clavier, le code se colle d'un coup.
                      SizedBox(
                        height: 60,
                        child: Stack(
                          children: [
                            Row(
                              children: [
                                for (var i = 0; i < 6; i++)
                                  Expanded(
                                    child: Container(
                                      height: 60,
                                      margin: EdgeInsets.only(
                                        right: i < 5 ? 8 : 0,
                                      ),
                                      alignment: Alignment.center,
                                      decoration: BoxDecoration(
                                        color: t.field,
                                        borderRadius: BorderRadius.circular(15),
                                        boxShadow: i == _code.text.length
                                            ? [
                                                BoxShadow(
                                                  color: p.soft,
                                                  spreadRadius: 5,
                                                ),
                                                const BoxShadow(
                                                  color: NexisColors.brand,
                                                  spreadRadius: 2,
                                                ),
                                              ]
                                            : [
                                                BoxShadow(
                                                  color: t.ring,
                                                  spreadRadius: 1.5,
                                                ),
                                              ],
                                      ),
                                      child: Text(
                                        i < _code.text.length
                                            ? _code.text[i]
                                            : '',
                                        style: title(24, color: p.ink),
                                      ),
                                    ),
                                  ),
                              ],
                            ),
                            Positioned.fill(
                              child: TextField(
                                controller: _code,
                                focusNode: _focus,
                                autofocus: true,
                                keyboardType: TextInputType.number,
                                autofillHints: const [
                                  AutofillHints.oneTimeCode,
                                ],
                                inputFormatters: [
                                  FilteringTextInputFormatter.digitsOnly,
                                  LengthLimitingTextInputFormatter(6),
                                ],
                                showCursor: false,
                                enableInteractiveSelection: false,
                                style: const TextStyle(
                                  color: Colors.transparent,
                                ),
                                decoration: const InputDecoration(
                                  border: InputBorder.none,
                                  enabledBorder: InputBorder.none,
                                  focusedBorder: InputBorder.none,
                                  filled: false,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const _LoginError(null),
                      const SizedBox(height: 10),
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              l.notReceived,
                              style: body(14.5, color: p.muted),
                            ),
                          ),
                          GestureDetector(
                            onTap: _left == 0 ? _resend : null,
                            child: Text(
                              _left == 0
                                  ? l.resendNow
                                  : l.resendIn(
                                      '${_left ~/ 60}:${(_left % 60).toString().padLeft(2, '0')}',
                                    ),
                              style: body(
                                14.5,
                                weight: FontWeight.w600,
                                color: _left == 0
                                    ? NexisColors.brand
                                    : const Color(0xFF8A95A8),
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 18),
                      Text(
                        l.codeHint,
                        style: body(13, color: p.muted).copyWith(height: 1.5),
                      ),
                      const SizedBox(height: 14),
                      for (final c in others)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 10),
                          child: GestureDetector(
                            behavior: HitTestBehavior.opaque,
                            onTap: () => _switchTo(c),
                            child: Text(
                              l.receiveInstead(c.label),
                              style: body(
                                14.5,
                                weight: FontWeight.w600,
                                color: NexisColors.brand,
                              ),
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
