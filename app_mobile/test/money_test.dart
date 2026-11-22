import 'package:flutter_test/flutter_test.dart';
import 'package:nexis_hub/data/money.dart';

void main() {
  test('francs congolais : groupes de trois, sans décimales', () {
    expect(formatMoney(const Money(25000, Currency.cdf), 'fr'), '25 000 FC');
    expect(
      formatMoney(const Money(1250000, Currency.cdf), 'ln'),
      '1 250 000 FC',
    );
    expect(formatMoney(const Money(900, Currency.cdf), 'fr'), '900 FC');
    expect(formatMoney(const Money(0, Currency.cdf), 'fr'), '0 FC');
  });

  test('dollars : toujours deux décimales', () {
    expect(formatMoney(const Money(500, Currency.usd), 'fr'), '5,00 USD');
    expect(formatMoney(const Money(1250, Currency.usd), 'fr'), '12,50 USD');
    expect(
      formatMoney(const Money(123456705, Currency.usd), 'fr'),
      '1 234 567,05 USD',
    );
  });

  test('anglais : virgule pour les milliers, point pour les cents', () {
    expect(formatMoney(const Money(25000, Currency.cdf), 'en'), '25,000 FC');
    expect(formatMoney(const Money(4500, Currency.usd), 'en'), '45.00 USD');
  });

  test('montant négatif (retrait)', () {
    expect(formatMoney(const Money(-2000, Currency.usd), 'fr'), '−20,00 USD');
  });
}
