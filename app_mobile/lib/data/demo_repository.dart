import 'models.dart';
import 'money.dart';
import 'repository.dart';

/// Données FICTIVES de l'aperçu. Aucun appel réseau, aucun argent.
class DemoRepository implements NexisRepository {
  DemoRepository({DateTime? now}) : _now = now ?? DateTime.now();

  final DateTime _now;

  @override
  Future<Profile> profile() async => const Profile(
    firstName: 'Grâce',
    lastName: 'Nsimba',
    phone: '+243812345412',
    commune: 'Limete',
    isProvider: false,
  );

  @override
  Future<Wallet> wallet() async => const Wallet(
    available: {
      Currency.cdf: Money(45000, Currency.cdf),
      Currency.usd: Money(1250, Currency.usd),
    },
    secured: {
      Currency.cdf: Money(35000, Currency.cdf),
      Currency.usd: Money(500, Currency.usd),
    },
  );

  @override
  Future<List<Mission>> missions() async => [
    Mission(
      id: 51,
      service: Service.plomberie,
      commune: 'Gombe',
      status: MissionStatus.inProgress,
      payment: PaymentState.secured,
      amount: const Money(500, Currency.usd),
      providerName: 'Jean M.',
      when: _now.subtract(const Duration(hours: 1)),
    ),
    Mission(
      id: 52,
      service: Service.nettoyage,
      commune: 'Limete',
      status: MissionStatus.quoted,
      payment: PaymentState.none,
      quotesCount: 3,
      when: _now.subtract(const Duration(hours: 3)),
    ),
    Mission(
      id: 53,
      service: Service.electricite,
      commune: 'Ngaliema',
      status: MissionStatus.pending,
      payment: PaymentState.none,
      when: _now.subtract(const Duration(minutes: 30)),
    ),
    Mission(
      id: 41,
      service: Service.plomberie,
      commune: 'Gombe',
      status: MissionStatus.completed,
      payment: PaymentState.released,
      amount: const Money(4500, Currency.usd),
      providerName: 'Jean M.',
      when: _now.subtract(const Duration(days: 2)),
      rated: true,
    ),
    Mission(
      id: 38,
      service: Service.nettoyage,
      commune: 'Limete',
      status: MissionStatus.completed,
      payment: PaymentState.released,
      amount: const Money(25000, Currency.cdf),
      providerName: 'Prisca K.',
      when: _now.subtract(const Duration(days: 6)),
      rated: true,
    ),
    Mission(
      id: 33,
      service: Service.electricite,
      commune: 'Limete',
      status: MissionStatus.completed,
      payment: PaymentState.released,
      amount: const Money(18000, Currency.cdf),
      providerName: 'Alain L.',
      when: _now.subtract(const Duration(days: 12)),
    ),
  ];

  @override
  Future<List<Movement>> movements() async => [
    Movement(
      kind: MovementKind.payment,
      label: 'Plomberie · Gombe',
      amount: const Money(-500, Currency.usd),
      when: _now.subtract(const Duration(hours: 1)),
      state: PaymentState.secured,
    ),
    Movement(
      kind: MovementKind.refund,
      label: 'Visite annulée',
      amount: const Money(10000, Currency.cdf),
      when: _now.subtract(const Duration(days: 1)),
      state: PaymentState.refunded,
    ),
    Movement(
      kind: MovementKind.release,
      label: 'Plomberie · Gombe',
      amount: const Money(-4500, Currency.usd),
      when: _now.subtract(const Duration(days: 2)),
      state: PaymentState.released,
    ),
    Movement(
      kind: MovementKind.release,
      label: 'Nettoyage · Limete',
      amount: const Money(-25000, Currency.cdf),
      when: _now.subtract(const Duration(days: 6)),
      state: PaymentState.released,
    ),
  ];
}
