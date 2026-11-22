import 'package:flutter_test/flutter_test.dart';
import 'package:nexis_hub/data/demo_repository.dart';
import 'package:nexis_hub/data/models.dart';
import 'package:nexis_hub/data/money.dart';
import 'package:nexis_hub/screens/provider/quote.dart';

void main() {
  test('le prix tapé : francs entiers, dollars à deux décimales', () {
    expect(parsePrice('25000', Currency.cdf)!.minorUnits, 25000);
    expect(parsePrice('25 000', Currency.cdf)!.minorUnits, 25000);
    expect(parsePrice('0', Currency.cdf), isNull);
    expect(parsePrice('12,5', Currency.cdf), isNull);
    expect(parsePrice('', Currency.cdf), isNull);
    expect(parsePrice('12,5', Currency.usd)!.minorUnits, 1250);
    expect(parsePrice('12.05', Currency.usd)!.minorUnits, 1205);
    expect(parsePrice('12.345', Currency.usd), isNull);
    expect(parsePrice('0.00', Currency.usd), isNull);
  });

  test('un devis part une seule fois, jamais à zéro', () async {
    final repo = DemoRepository();
    final slot = DateTime.now().add(const Duration(days: 1));
    expect(
      () => repo.sendQuote(71, const Money(0, Currency.cdf), slot),
      throwsArgumentError,
    );
    await repo.sendQuote(71, const Money(25000, Currency.cdf), slot);
    expect((await repo.providerRequest(71)).quoted, isTrue);
    expect(
      () => repo.sendQuote(71, const Money(25000, Currency.cdf), slot),
      throwsStateError,
    );
  });

  test('« Je suis arrivé » seul ne confirme rien', () async {
    final repo = DemoRepository();
    final job = await repo.signalArrival(61);
    expect(job.arrivalSignaled, isTrue);
    expect(job.steps.containsKey(ProviderStep.arrived), isFalse);
    expect(() => repo.finishJob(61), throwsStateError);
  });

  test(
    'le code de présence : bon code confirme, cinq erreurs bloquent',
    () async {
      final repo = DemoRepository();
      await repo.signalArrival(61);
      for (var i = 0; i < 4; i++) {
        expect(
          await repo.enterPresenceCode(61, '0000'),
          PresenceResult.wrongCode,
        );
      }
      expect(await repo.enterPresenceCode(61, '0000'), PresenceResult.locked);
      expect(
        await repo.enterPresenceCode(61, DemoRepository.demoPresenceCode),
        PresenceResult.locked,
      );

      final other = DemoRepository();
      await other.signalArrival(61);
      expect(
        await other.enterPresenceCode(61, DemoRepository.demoPresenceCode),
        PresenceResult.confirmed,
      );
      final done = await other.finishJob(61);
      expect(done.steps.containsKey(ProviderStep.finished), isTrue);
      expect((await other.providerHome()).secured.minorUnits, 0);
    },
  );
}
