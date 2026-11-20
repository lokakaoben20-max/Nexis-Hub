import 'package:flutter_test/flutter_test.dart';
import 'package:nexis_hub/data/demo_repository.dart';
import 'package:nexis_hub/data/models.dart';
import 'package:nexis_hub/data/money.dart';
import 'package:nexis_hub/ui/dates.dart';

void main() {
  test('les devis arrivent le mieux noté en premier', () async {
    final repo = DemoRepository();
    final quotes = await repo.quotes(52);
    expect(quotes.map((q) => q.providerName), ['Prisca K.', 'Joël M.', 'Aline L.']);
  });

  test('payer un devis sécurise exactement le montant du devis', () async {
    final repo = DemoRepository();
    final quote = (await repo.quotes(52)).firstWhere((q) => q.id == 522);
    final paid = await repo.pay(52, 522, MobileOperator.mpesa);
    expect(paid.status, MissionStatus.confirmed);
    expect(paid.payment, PaymentState.secured);
    expect(paid.amount!.minorUnits, quote.price.minorUnits);
    expect(paid.amount!.currency, Currency.cdf);
    expect(paid.chosen!.providerName, 'Joël M.');
    expect(paid.steps.keys, [TrackStep.paid]);
    final movements = await repo.movements();
    expect(movements.first.state, PaymentState.secured);
  });

  test('confirmer verse l\'argent au prestataire', () async {
    final repo = DemoRepository();
    final done = await repo.confirmDone(49);
    expect(done.status, MissionStatus.completed);
    expect(done.payment, PaymentState.released);
    expect(done.steps.containsKey(TrackStep.confirmed), isTrue);
  });

  test('créneaux dans les trois langues', () {
    final saturday = DateTime(2026, 11, 21, 9);
    expect(formatSlot(saturday, 'fr', capital: true), 'Samedi 9 h');
    expect(formatSlot(DateTime(2026, 11, 21, 8, 41), 'fr'), 'samedi 8 h 41');
    expect(formatSlot(saturday, 'en'), 'Saturday 9 am');
    expect(formatSlot(saturday, 'ln'), 'mposɔ 9 h');
  });
}
