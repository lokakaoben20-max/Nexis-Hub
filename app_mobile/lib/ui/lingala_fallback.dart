import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

// Flutter ne fournit pas ses propres textes (boutons système, dates) en
// lingala : pour le lingala, ces textes système viennent du français.
// Tous les textes de Nexis, eux, sont traduits dans lib/l10n/app_ln.arb.

class _Fallback<T> extends LocalizationsDelegate<T> {
  const _Fallback(this.inner);
  final LocalizationsDelegate<T> inner;

  Locale _map(Locale locale) =>
      locale.languageCode == 'ln' ? const Locale('fr') : locale;

  @override
  bool isSupported(Locale locale) => inner.isSupported(_map(locale));

  @override
  Future<T> load(Locale locale) => inner.load(_map(locale));

  @override
  bool shouldReload(covariant LocalizationsDelegate<T> old) => false;
}

const List<LocalizationsDelegate<dynamic>> systemDelegates = [
  _Fallback<MaterialLocalizations>(GlobalMaterialLocalizations.delegate),
  _Fallback<CupertinoLocalizations>(GlobalCupertinoLocalizations.delegate),
  _Fallback<WidgetsLocalizations>(GlobalWidgetsLocalizations.delegate),
];
