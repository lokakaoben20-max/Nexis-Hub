import 'package:flutter_test/flutter_test.dart';
import 'package:nexis_hub/data/demo_repository.dart';
import 'package:nexis_hub/data/models.dart';
import 'package:nexis_hub/data/money.dart';
import 'package:nexis_hub/ui/dates.dart';

void main() {
  test('les devis arrivent le mieux noté en premier', () async {
    final repo = DemoRepository();
    final quotes = await repo.quotes(52);
    expect(quotes.map((q) => q.providerName), [
      'Prisca K.',
      'Joël M.',
      'Aline L.',
    ]);
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

  test('signaler un problème bloque l\'argent de la mission', () async {
    final repo = DemoRepository();
    final dispute = await repo.reportProblem(
      49,
      DisputeReason.badWork,
      '  Les pointes ne sont pas faites.  ',
    );
    expect(dispute.text, 'Les pointes ne sont pas faites.');
    expect(dispute.decided, isFalse);
    final mission = await repo.mission(49);
    expect(mission.status, MissionStatus.disputed);
    expect(mission.payment, PaymentState.blocked);
    expect(mission.amount!.minorUnits, 15000);
    expect(mission.isActive, isTrue);
    expect((await repo.dispute(49))!.reason, DisputeReason.badWork);
  });

  test(
    'pas de signalement sur une mission terminée ou déjà en litige',
    () async {
      final repo = DemoRepository();
      expect(
        () => repo.reportProblem(41, DisputeReason.other, 'x'),
        throwsStateError,
      );
      await repo.reportProblem(49, DisputeReason.other, 'x');
      expect(
        () => repo.reportProblem(49, DisputeReason.other, 'y'),
        throwsStateError,
      );
    },
  );

  test('jours restants pour contester et heure des événements', () {
    final now = DateTime(2026, 11, 20, 10);
    expect(daysLeft(now.add(const Duration(days: 3)), now: now), 3);
    expect(daysLeft(now.add(const Duration(hours: 70)), now: now), 3);
    expect(daysLeft(now.add(const Duration(hours: 5)), now: now), 1);
    expect(daysLeft(now.subtract(const Duration(hours: 1)), now: now), 0);
    expect(formatStamp(DateTime(2026, 11, 20, 13), 'fr', now: now), '13 h');
    expect(
      formatStamp(DateTime(2026, 11, 14, 13), 'fr', now: now),
      'sam. 13 h',
    );
    expect(formatStamp(DateTime(2026, 11, 14, 13), 'en', now: now), 'Sat 1 pm');
  });
}
