// Montants : la seule façon d'afficher de l'argent dans l'app.
//
// L'app ne calcule jamais d'argent : elle affiche les montants que le
// serveur Nexis lui envoie (en unités mineures, sans virgule flottante),
// avec les règles de la charte : « 25 000 FC » sans décimales et
// « 12,50 USD » toujours avec deux décimales.

enum Currency { cdf, usd }

class Money {
  const Money(this.minorUnits, this.currency);

  /// Francs congolais : en francs (pas de centimes affichés).
  /// Dollars : en cents.
  final int minorUnits;
  final Currency currency;

  bool get isZero => minorUnits == 0;
}

String formatMoney(Money money, String languageCode) {
  final english = languageCode == 'en';
  final group = english
      ? ','
      : ' '; // espace fine insécable en français et lingala
  final negative = money.minorUnits < 0;
  final absolute = money.minorUnits.abs();
  String grouped(int value) {
    final digits = value.toString();
    final buffer = StringBuffer();
    for (var i = 0; i < digits.length; i++) {
      if (i > 0 && (digits.length - i) % 3 == 0) buffer.write(group);
      buffer.write(digits[i]);
    }
    return buffer.toString();
  }

  final sign = negative ? '−' : '';
  switch (money.currency) {
    case Currency.cdf:
      return '$sign${grouped(absolute)} FC';
    case Currency.usd:
      final units = grouped(absolute ~/ 100);
      final cents = (absolute % 100).toString().padLeft(2, '0');
      return '$sign$units${english ? '.' : ','}$cents USD';
  }
}
