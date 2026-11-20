import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../ui/icons.dart';

import '../app_state.dart';
import '../l10n/app_localizations.dart';
import '../ui/common.dart';
import '../ui/theme.dart';
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
  late final AnimationController _orbit = AnimationController(
    vsync: this,
    duration: const Duration(seconds: 38),
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
      return;
    }
    _intro.forward();
    _orbit.repeat();
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
    _orbit.dispose();
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
          animation: Listenable.merge([_intro, _orbit, _breath, _shine]),
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
                                child: IntroFade(
                                  seconds: s,
                                  start: .7,
                                  end: 1.3,
                                  rise: 0,
                                  child: ServiceOrbit(
                                    seconds: s,
                                    turn: _orbit.value,
                                  ),
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
                                  onTap: () => _toNumber(context),
                                ),
                              ),
                              const SizedBox(height: 10),
                              _WhiteButton(
                                label: l.haveAccount,
                                filled: false,
                                onTap: () => _toNumber(context),
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

  void _toNumber(BuildContext context) =>
      Navigator.of(context)
          .push(MaterialPageRoute<void>(builder: (_) => const NumberScreen()));
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

class _Steps extends StatelessWidget {
  const _Steps(this.done);

  final int done;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      for (var i = 0; i < 4; i++)
        Expanded(
          child: Container(
            height: 4,
            margin: EdgeInsets.only(right: i < 3 ? 6 : 0),
            decoration: BoxDecoration(
              color: i < done ? NexisColors.brand : context.palette.line,
              borderRadius: BorderRadius.circular(9),
            ),
          ),
        ),
    ],
  );
}

enum _Channel { whatsapp, telegram }

/// 16 : numéro (+243) et canal du code, WhatsApp ou Telegram.
class NumberScreen extends StatefulWidget {
  const NumberScreen({super.key});

  @override
  State<NumberScreen> createState() => _NumberScreenState();
}

class _NumberScreenState extends State<NumberScreen> {
  final _phone = TextEditingController();
  _Channel _channel = _Channel.whatsapp;

  bool get _valid => _phone.text.replaceAll(RegExp(r'\D'), '').length == 9;

  @override
  void dispose() {
    _phone.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    return Scaffold(
      appBar: roundBackBar(context),
      body: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(18, 4, 18, 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const _Steps(1),
              const SizedBox(height: 24),
              Text(l.yourNumber, style: title(22, color: p.ink)),
              const SizedBox(height: 8),
              Text(l.yourNumberIntro, style: body(13.5, color: p.muted)),
              const SizedBox(height: 20),
              Row(
                children: [
                  Container(
                    height: 56,
                    padding: const EdgeInsets.symmetric(horizontal: 14),
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: p.surface,
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: p.line),
                    ),
                    child: Text(
                      '🇨🇩 +243',
                      style: body(16, weight: FontWeight.w600, color: p.ink),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: TextField(
                      controller: _phone,
                      autofocus: false,
                      keyboardType: TextInputType.phone,
                      inputFormatters: [
                        FilteringTextInputFormatter.digitsOnly,
                        LengthLimitingTextInputFormatter(9),
                      ],
                      onChanged: (_) => setState(() {}),
                      style: title(20, color: p.ink),
                      decoration: InputDecoration(
                        hintText: '81 234 54 12',
                        hintStyle: title(
                          20,
                          color: p.muted.withValues(alpha: .5),
                        ),
                        filled: true,
                        fillColor: p.surface,
                        contentPadding: const EdgeInsets.symmetric(
                          horizontal: 14,
                          vertical: 16,
                        ),
                        enabledBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(14),
                          borderSide: BorderSide(color: p.line),
                        ),
                        focusedBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(14),
                          borderSide: const BorderSide(
                            color: NexisColors.brand,
                            width: 2,
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 22),
              Text(
                l.receiveCodeBy,
                style: body(14, weight: FontWeight.w600, color: p.ink),
              ),
              const SizedBox(height: 10),
              _channelTile(
                _Channel.whatsapp,
                'WhatsApp',
                l.whatsappSub,
                PhFill.whatsappLogo,
                const Color(0xFF25D366),
              ),
              const SizedBox(height: 10),
              _channelTile(
                _Channel.telegram,
                'Telegram',
                l.telegramSub,
                PhFill.telegramLogo,
                const Color(0xFF2AABEE),
              ),
              const Spacer(),
              _Legal(l: l),
              const SizedBox(height: 12),
              PrimaryButton(
                label: l.receiveCode,
                onPressed: _valid
                    ? () => Navigator.of(context).push(
                        MaterialPageRoute<void>(
                          builder: (_) => CodeScreen(
                            phone: _phone.text,
                            channel: _channel == _Channel.whatsapp
                                ? 'WhatsApp'
                                : 'Telegram',
                          ),
                        ),
                      )
                    : null,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _channelTile(
    _Channel channel,
    String name,
    String sub,
    IconData icon,
    Color color,
  ) {
    final p = context.palette;
    final selected = _channel == channel;
    return Material(
      color: p.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(
          color: selected ? NexisColors.brand : p.line,
          width: selected ? 2 : 1,
        ),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () => setState(() => _channel = channel),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          child: Row(
            children: [
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  color: color,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(icon, color: Colors.white, size: 22),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      name,
                      style: body(14, weight: FontWeight.w700, color: p.ink),
                    ),
                    const SizedBox(height: 1),
                    Text(sub, style: body(12, color: p.muted)),
                  ],
                ),
              ),
              AnimatedContainer(
                duration: const Duration(milliseconds: 150),
                width: 20,
                height: 20,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: selected
                        ? NexisColors.brand
                        : const Color(0xFFC9D0DB),
                    width: selected ? 6 : 2,
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

/// 17 : le code à 6 chiffres.
class CodeScreen extends StatefulWidget {
  const CodeScreen({super.key, required this.phone, required this.channel});

  final String phone;
  final String channel;

  @override
  State<CodeScreen> createState() => _CodeScreenState();
}

class _CodeScreenState extends State<CodeScreen> {
  final _code = TextEditingController();
  final _focus = FocusNode();
  Timer? _timer;
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

  @override
  void initState() {
    super.initState();
    _restart();
    _code.addListener(() {
      setState(() {});
      if (_code.text.length == 6) {
        // Aperçu : n'importe quel code est accepté. La vraie app envoie le
        // code au serveur (backend/app/app_auth.py) qui seul décide.
        Future<void>.delayed(const Duration(milliseconds: 250), () {
          if (!mounted) return;
          Navigator.of(context).popUntil((route) => route.isFirst);
          AppScope.of(context).signIn();
        });
      }
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    _code.dispose();
    _focus.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final p = context.palette;
    final digits = widget.phone.replaceAll(RegExp(r'\D'), '');
    final masked =
        '+243 ${digits.substring(0, 2)} •• •• ${digits.substring(digits.length - 3)}';
    return Scaffold(
      appBar: roundBackBar(context),
      body: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(18, 4, 18, 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const _Steps(2),
              const SizedBox(height: 24),
              Text(l.theCode, style: title(22, color: p.ink)),
              const SizedBox(height: 8),
              Text(
                l.codeSentTo(widget.channel, masked),
                style: body(13.5, color: p.muted),
              ),
              const SizedBox(height: 22),
              // Le vrai champ couvre les six cases, invisible : toucher une
              // case ouvre le clavier, le code se colle d'un coup.
              SizedBox(
                height: 54,
                child: Stack(
                  children: [
                    Row(
                      children: [
                        for (var i = 0; i < 6; i++)
                          Expanded(
                            child: Container(
                              height: 54,
                              margin: EdgeInsets.only(right: i < 5 ? 8 : 0),
                              alignment: Alignment.center,
                              decoration: BoxDecoration(
                                color: p.surface,
                                borderRadius: BorderRadius.circular(14),
                                border: Border.all(
                                  color: i == _code.text.length
                                      ? NexisColors.brand
                                      : i < _code.text.length
                                      ? p.ink
                                      : p.line,
                                  width: i == _code.text.length
                                      ? 2
                                      : i < _code.text.length
                                      ? 1.5
                                      : 1,
                                ),
                                boxShadow: i == _code.text.length
                                    ? const [
                                        BoxShadow(
                                          color: Color(0xFFDCEBFF),
                                          spreadRadius: 3,
                                        ),
                                      ]
                                    : null,
                              ),
                              child: i == _code.text.length
                                  ? Container(
                                      width: 2,
                                      height: 22,
                                      color: NexisColors.brand,
                                    )
                                  : Text(
                                      i < _code.text.length
                                          ? _code.text[i]
                                          : '',
                                      style: title(20, color: p.ink),
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
                        autofillHints: const [AutofillHints.oneTimeCode],
                        inputFormatters: [
                          FilteringTextInputFormatter.digitsOnly,
                          LengthLimitingTextInputFormatter(6),
                        ],
                        showCursor: false,
                        enableInteractiveSelection: false,
                        style: const TextStyle(color: Colors.transparent),
                        decoration: const InputDecoration(
                          border: InputBorder.none,
                          filled: false,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 14),
              Row(
                children: [
                  Expanded(
                    child: Text(
                      l.notReceived,
                      style: body(12.5, color: p.muted),
                    ),
                  ),
                  GestureDetector(
                    onTap: _left == 0 ? _restart : null,
                    child: Text(
                      _left == 0
                          ? l.resendNow
                          : l.resendIn(
                              '${_left ~/ 60}:${(_left % 60).toString().padLeft(2, '0')}',
                            ),
                      style: body(
                        12.5,
                        weight: FontWeight.w600,
                        color: NexisColors.brand,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              Center(
                child: GestureDetector(
                  onTap: () => Navigator.of(context).pop(),
                  child: Text(
                    l.receiveInstead(
                      widget.channel == 'WhatsApp' ? 'Telegram' : 'WhatsApp',
                    ),
                    style: body(
                      13,
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
    );
  }
}

/// Liens légaux juste au-dessus du bouton (maquette 16).
class _Legal extends StatelessWidget {
  const _Legal({required this.l});

  final AppLocalizations l;

  @override
  Widget build(BuildContext context) {
    final muted = context.palette.muted;
    const marker = '\u0001';
    final parts = l.legalText(marker, '\u0002').split(RegExp('[\u0001\u0002]'));
    final link = body(11.5, weight: FontWeight.w600, color: NexisColors.brand);
    final order =
        l.legalText(marker, '\u0002').indexOf(marker) <
            l.legalText(marker, '\u0002').indexOf('\u0002')
        ? [l.legalTerms, l.legalPrivacy]
        : [l.legalPrivacy, l.legalTerms];
    return Text.rich(
      TextSpan(
        style: body(11.5, color: muted).copyWith(height: 1.5),
        children: [
          TextSpan(text: parts[0]),
          TextSpan(text: order[0], style: link),
          TextSpan(text: parts[1]),
          TextSpan(text: order[1], style: link),
          TextSpan(text: parts.length > 2 ? parts[2] : ''),
        ],
      ),
      textAlign: TextAlign.center,
    );
  }
}
