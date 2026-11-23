import 'package:flutter/material.dart';

import '../app_state.dart';
import '../l10n/app_localizations.dart';
import '../ui/nx_parts.dart';
import '../ui/parts.dart';
import '../ui/theme.dart';

/// Le profil d'un nouveau client de l'aperçu, après le code fictif.
class SignupScreen extends StatefulWidget {
  const SignupScreen({super.key, required this.phone});

  final String phone;

  @override
  State<SignupScreen> createState() => _SignupScreenState();
}

class _SignupScreenState extends State<SignupScreen> {
  final _firstName = TextEditingController();
  final _lastName = TextEditingController();
  String? _commune;
  bool _accepted = false;
  bool _failed = false;

  bool get _complete =>
      _firstName.text.trim().isNotEmpty &&
      _lastName.text.trim().isNotEmpty &&
      _commune != null &&
      _accepted;

  @override
  void dispose() {
    _firstName.dispose();
    _lastName.dispose();
    super.dispose();
  }

  void _submit() {
    if (!_complete) return;
    final repo = AppScope.of(context).repository;
    final created = repo.registerDemoClient(
      phone: widget.phone,
      firstName: _firstName.text,
      lastName: _lastName.text,
      commune: _commune!,
      acceptedTermsVersion: _accepted ? repo.signupTermsVersion : null,
    );
    if (created) {
      Navigator.of(context).pop(true);
    } else {
      setState(() => _failed = true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final repo = AppScope.of(context).repository;
    final p = context.palette;
    return NScreen(
      bottom: NButton(
        label: l.signupCreateProfile,
        onPressed: _complete ? _submit : null,
      ),
      children: [
        NTopBar(title: l.signupTitle),
        Text(l.signupDemoNotice, style: body(14, color: mutedColor(context))),
        TextField(
          controller: _firstName,
          textCapitalization: TextCapitalization.words,
          textInputAction: TextInputAction.next,
          autofillHints: const [AutofillHints.givenName],
          maxLength: 100,
          decoration: InputDecoration(
            labelText: l.signupFirstName,
            counterText: '',
          ),
          onChanged: (_) => setState(() => _failed = false),
        ),
        TextField(
          controller: _lastName,
          textCapitalization: TextCapitalization.words,
          textInputAction: TextInputAction.next,
          autofillHints: const [AutofillHints.familyName],
          maxLength: 100,
          decoration: InputDecoration(
            labelText: l.signupLastName,
            counterText: '',
          ),
          onChanged: (_) => setState(() => _failed = false),
        ),
        DropdownButtonFormField<String>(
          initialValue: _commune,
          isExpanded: true,
          decoration: InputDecoration(labelText: l.commune),
          items: [
            for (final commune in repo.communes)
              DropdownMenuItem(value: commune, child: Text(commune)),
          ],
          onChanged: (value) => setState(() {
            _commune = value;
            _failed = false;
          }),
        ),
        NCard(
          child: Material(
            type: MaterialType.transparency,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(l.legalTerms, style: title(14, color: p.ink)),
                Text(
                  l.termsVersion(longDate(context, repo.signupTermsVersion)),
                  style: body(13, color: mutedColor(context)),
                ),
                TextButton(
                  onPressed: () => Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (context) => NScreen(
                        children: [
                          NTopBar(title: l.signupReadTerms),
                          Text(
                            l.termsVersion(
                              longDate(context, repo.signupTermsVersion),
                            ),
                          ),
                          Text(
                            l.signupDemoTerms,
                            style: body(15, color: p.ink),
                          ),
                        ],
                      ),
                    ),
                  ),
                  child: Text(l.signupReadTerms),
                ),
                CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  controlAffinity: ListTileControlAffinity.leading,
                  title: Text(l.signupAcceptTerms),
                  value: _accepted,
                  onChanged: (value) => setState(() {
                    _accepted = value ?? false;
                    _failed = false;
                  }),
                ),
              ],
            ),
          ),
        ),
        if (_failed) Text(l.signupFailed, style: body(14, color: p.ink)),
      ],
    );
  }
}
