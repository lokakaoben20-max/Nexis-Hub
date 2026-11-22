import 'package:flutter/services.dart';

/// Opérateurs mobiles de la RDC, d'après les préfixes à deux chiffres qui
/// suivent +243. Contrôle de confort à la saisie seulement : le serveur reste
/// seul juge du numéro (voir backend/app/app_auth.py).
enum Operator {
  vodacom('Vodacom', {'81', '82', '83'}),
  airtel('Airtel', {'97', '98', '99'}),
  orange('Orange', {'80', '84', '85', '89'}),
  africell('Africell', {'90', '91'});

  const Operator(this.label, this.prefixes);

  final String label;
  final Set<String> prefixes;
}

/// Le numéro national saisi : 9 chiffres, sans le 0 d'appel ni le +243.
class DrcPhone {
  const DrcPhone._(this.digits);

  /// Chiffres nationaux, 9 au plus.
  final String digits;

  static const length = 9;

  /// Garde les chiffres, retire un +243 / 00243 / 243 ou un 0 d'appel collé
  /// en tête, et coupe à 9 chiffres.
  static DrcPhone parse(String raw) {
    var d = raw.replaceAll(RegExp(r'\D'), '');
    if (d.startsWith('00243')) {
      d = d.substring(5);
    } else if (d.startsWith('243') && d.length > length) {
      d = d.substring(3);
    } else if (d.startsWith('0')) {
      d = d.substring(1);
    }
    if (d.length > length) d = d.substring(0, length);
    return DrcPhone._(d);
  }

  bool get isComplete => digits.length == length;

  /// Le préfixe est connu dès deux chiffres saisis.
  Operator? get operator {
    if (digits.length < 2) return null;
    final prefix = digits.substring(0, 2);
    for (final o in Operator.values) {
      if (o.prefixes.contains(prefix)) return o;
    }
    return null;
  }

  /// Faux dès que les deux premiers chiffres ne sont ceux d'aucun opérateur.
  bool get prefixKnown => digits.length < 2 || operator != null;

  /// Vrai seulement pour un numéro complet d'un opérateur connu.
  bool get isValid => isComplete && operator != null;

  /// `81 234 54 12`.
  String get formatted {
    final parts = <String>[];
    const cuts = [2, 3, 2, 2];
    var i = 0;
    for (final n in cuts) {
      if (i >= digits.length) break;
      final end = i + n > digits.length ? digits.length : i + n;
      parts.add(digits.substring(i, end));
      i = end;
    }
    return parts.join(' ');
  }

  /// Format international attendu par le serveur : `+243812345454`.
  String get e164 => '+243$digits';
}

/// Met le numéro en forme à chaque frappe en gardant le curseur à la fin des
/// chiffres déjà saisis.
class DrcPhoneFormatter extends TextInputFormatter {
  const DrcPhoneFormatter();

  @override
  TextEditingValue formatEditUpdate(
    TextEditingValue oldValue,
    TextEditingValue newValue,
  ) {
    final text = DrcPhone.parse(newValue.text).formatted;
    return TextEditingValue(
      text: text,
      selection: TextSelection.collapsed(offset: text.length),
    );
  }
}
