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

  late final List<Mission> _missions = [
    Mission(
      id: 51,
      service: Service.plomberie,
      commune: 'Gombe',
      status: MissionStatus.inProgress,
      payment: PaymentState.secured,
      amount: const Money(500, Currency.usd),
      providerName: 'Jean M.',
      when: _now.subtract(const Duration(hours: 1)),
      chosen: Quote(
        id: 511,
        providerName: 'Jean M.',
        initials: 'JM',
        avatarColor: 0xFF1E7A5C,
        rating: 4.8,
        reviews: 92,
        price: const Money(500, Currency.usd),
        slot: _now.add(const Duration(minutes: 40)),
      ),
      distanceKm: 2.4,
      steps: {
        TrackStep.paid: _now.subtract(const Duration(minutes: 30)),
        TrackStep.onTheWay: _now.subtract(const Duration(minutes: 19)),
      },
    ),
    Mission(
      id: 52,
      service: Service.nettoyage,
      commune: 'Limete',
      status: MissionStatus.quoted,
      payment: PaymentState.none,
      quotesCount: 3,
      when: _now.subtract(const Duration(hours: 3)),
      detail: '3 pièces',
      wanted: 'Samedi matin',
    ),
    Mission(
      id: 49,
      service: Service.coiffure,
      commune: 'Limete',
      status: MissionStatus.awaitingConfirmation,
      payment: PaymentState.secured,
      amount: const Money(15000, Currency.cdf),
      providerName: 'Nadia K.',
      when: _now.subtract(const Duration(hours: 5)),
      chosen: Quote(
        id: 491,
        providerName: 'Nadia K.',
        initials: 'NK',
        avatarColor: 0xFFC2416B,
        rating: 4.9,
        reviews: 57,
        price: const Money(15000, Currency.cdf),
        slot: _now.subtract(const Duration(hours: 3)),
      ),
      steps: {
        TrackStep.paid: _now.subtract(const Duration(hours: 5)),
        TrackStep.onTheWay: _now.subtract(
          const Duration(hours: 3, minutes: 30),
        ),
        TrackStep.onSite: _now.subtract(const Duration(hours: 3)),
        TrackStep.workDone: _now.subtract(const Duration(minutes: 20)),
      },
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

  late final List<Movement> _movements = [
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

  /// Samedi prochain à [hour] h, pour les créneaux des devis.
  DateTime _saturday(int hour) {
    final days = (DateTime.saturday - _now.weekday + 7) % 7;
    final day = _now.add(Duration(days: days == 0 ? 7 : days));
    return DateTime(day.year, day.month, day.day, hour);
  }

  late final Map<int, List<Quote>> _quotes = {
    52: [
      Quote(
        id: 521,
        providerName: 'Prisca K.',
        initials: 'PK',
        avatarColor: 0xFF494C95,
        rating: 4.9,
        reviews: 128,
        price: const Money(25000, Currency.cdf),
        slot: _saturday(9),
      ),
      Quote(
        id: 522,
        providerName: 'Joël M.',
        initials: 'JM',
        avatarColor: 0xFF1E7A5C,
        rating: 4.7,
        reviews: 64,
        price: const Money(22000, Currency.cdf),
        slot: _saturday(10),
      ),
      Quote(
        id: 523,
        providerName: 'Aline L.',
        initials: 'AL',
        avatarColor: 0xFFC98200,
        rating: 4.6,
        reviews: 31,
        price: const Money(28000, Currency.cdf),
        slot: _saturday(8),
      ),
    ],
  };

  @override
  Future<List<Mission>> missions() async => List.of(_missions);

  @override
  Future<List<Movement>> movements() async => List.of(_movements);

  @override
  Future<Mission> mission(int id) async =>
      _missions.firstWhere((m) => m.id == id);

  @override
  Future<List<Quote>> quotes(int missionId) async {
    final list = List.of(_quotes[missionId] ?? const <Quote>[]);
    list.sort((a, b) => b.rating.compareTo(a.rating));
    return list;
  }

  @override
  Future<List<PayAccount>> payAccounts() async => const [
    PayAccount(MobileOperator.mpesa, '+243 81 •• •• 412'),
    PayAccount(MobileOperator.orange, '+243 89 •• •• 207'),
    PayAccount(MobileOperator.airtel, null),
  ];

  void _replace(Mission updated) {
    final i = _missions.indexWhere((m) => m.id == updated.id);
    _missions[i] = updated;
  }

  @override
  Future<Mission> pay(
    int missionId,
    int quoteId,
    MobileOperator operator,
  ) async {
    final mission = await this.mission(missionId);
    final quote = _quotes[missionId]!.firstWhere((q) => q.id == quoteId);
    // Démonstration : l'opérateur accepte après quelques secondes.
    await Future<void>.delayed(const Duration(seconds: 3));
    final paid = mission.copyWith(
      status: MissionStatus.confirmed,
      payment: PaymentState.secured,
      amount: quote.price,
      providerName: quote.providerName,
      chosen: quote,
      steps: {TrackStep.paid: DateTime.now()},
    );
    _replace(paid);
    _movements.insert(
      0,
      Movement(
        kind: MovementKind.payment,
        label: '${_label(mission.service)} · ${mission.commune}',
        amount: Money(-quote.price.minorUnits, quote.price.currency),
        when: DateTime.now(),
        state: PaymentState.secured,
      ),
    );
    return paid;
  }

  @override
  Future<Mission> confirmDone(int missionId) async {
    final mission = await this.mission(missionId);
    final done = mission.copyWith(
      status: MissionStatus.completed,
      payment: PaymentState.released,
      steps: {...mission.steps, TrackStep.confirmed: DateTime.now()},
    );
    _replace(done);
    return done;
  }

  static String _label(Service service) => switch (service) {
    Service.nettoyage => 'Nettoyage',
    Service.plomberie => 'Plomberie',
    Service.electricite => 'Électricité',
    Service.coiffure => 'Coiffure',
    _ => service.name,
  };
}
