import 'models.dart';
import 'money.dart';
import 'repository.dart';

/// Données FICTIVES de l'aperçu. Aucun appel réseau, aucun argent.
class DemoRepository implements NexisRepository {
  DemoRepository({DateTime? now}) : _now = now ?? DateTime.now();

  final DateTime _now;

  /// Aperçu : tout est fictif ici, le code aussi. La vraie connexion lira
  /// les canaux réellement disponibles auprès du serveur.
  @override
  Set<String> get codeChannels => const {'whatsapp', 'telegram', 'sms'};

  static const _samplePhone = '+243812345412';
  String _activePhone = _samplePhone;
  final _registeredClients = <String, Profile>{};

  @override
  bool openDemoAccount(String phone) {
    if (phone != _samplePhone && !_registeredClients.containsKey(phone)) {
      return false;
    }
    _activePhone = phone;
    return true;
  }

  @override
  List<String> get signupCommunes => [
    ...serviceRequestCommunes,
    'Autre commune',
  ];

  @override
  List<String> get serviceRequestCommunes => const [
    'Bandalungwa',
    'Barumbu',
    'Bumbu',
    'Gombe',
    'Kalamu',
    'Kasa-Vubu',
    'Kimbanseke',
    'Kinshasa',
    'Kintambo',
    'Kisenso',
    'Lemba',
    'Limete',
    'Lingwala',
    'Makala',
    'Maluku',
    'Masina',
    'Matete',
    'Mont-Ngafula',
    "N'djili",
    'Ngaba',
    'Ngaliema',
    'Ngiri-Ngiri',
    "N'sele",
    'Selembao',
  ];

  @override
  DateTime get signupTermsVersion => DateTime(2026, 11, 20);

  @override
  bool registerDemoClient({
    required String phone,
    required String firstName,
    required String lastName,
    required String commune,
    required DateTime? acceptedTermsVersion,
  }) {
    final first = firstName.trim();
    final last = lastName.trim();
    if (phone == _samplePhone ||
        _registeredClients.containsKey(phone) ||
        first.isEmpty ||
        last.isEmpty ||
        !signupCommunes.contains(commune) ||
        acceptedTermsVersion != signupTermsVersion) {
      return false;
    }
    _registeredClients[phone] = Profile(
      firstName: first,
      lastName: last,
      phone: phone,
      commune: commune,
      isProvider: false,
      termsVersion: acceptedTermsVersion,
    );
    _activePhone = phone;
    return true;
  }

  @override
  Future<Profile> profile() async =>
      _registeredClients[_activePhone] ?? _sampleProfile;

  late final _sampleProfile = Profile(
    firstName: 'Grâce',
    lastName: 'Nsimba',
    phone: _samplePhone,
    commune: 'Limete',
    isProvider: true,
    termsVersion: signupTermsVersion,
  );

  @override
  Future<Wallet> wallet() async => _activePhone != _samplePhone
      ? const Wallet(available: {}, secured: {})
      : const Wallet(
          available: {
            Currency.cdf: Money(45000, Currency.cdf),
            Currency.usd: Money(1250, Currency.usd),
          },
          secured: {
            Currency.cdf: Money(35000, Currency.cdf),
            Currency.usd: Money(500, Currency.usd),
          },
        );

  final _requestedMissions = <String, List<Mission>>{};
  int _nextRequestId = 1000;

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
      id: 47,
      service: Service.climatisation,
      commune: 'Bandal',
      status: MissionStatus.disputed,
      payment: PaymentState.blocked,
      amount: const Money(6000, Currency.usd),
      providerName: 'Rodrigue T.',
      when: _now.subtract(const Duration(days: 1)),
    ),
    Mission(
      id: 44,
      service: Service.jardinage,
      commune: 'Ngaliema',
      status: MissionStatus.disputed,
      payment: PaymentState.blocked,
      amount: const Money(30000, Currency.cdf),
      providerName: 'Patrick B.',
      when: _now.subtract(const Duration(days: 4)),
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
      providerRating: 4.8,
      providerReviews: 92,
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
      providerRating: 4.9,
      providerReviews: 212,
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
      providerRating: 4.6,
      providerReviews: 58,
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

  late final Map<int, Dispute> _disputes = {
    47: Dispute(
      missionId: 47,
      reason: DisputeReason.badWork,
      text: "Le climatiseur coule encore dans la chambre.",
      photos: 2,
      openedAt: _now.subtract(const Duration(hours: 20)),
      providerReply: 'Je peux repasser demain matin.',
      providerRepliedAt: _now.subtract(const Duration(hours: 17)),
    ),
    44: Dispute(
      missionId: 44,
      reason: DisputeReason.notFinished,
      text: "La haie du fond n'a pas été taillée.",
      photos: 1,
      openedAt: _now.subtract(const Duration(days: 3)),
      outcome: DisputeOutcome.refund,
      decidedAt: _now.subtract(const Duration(hours: 2)),
      clientAmount: const Money(30000, Currency.cdf),
      providerAmount: const Money(0, Currency.cdf),
      contestUntil: _now
          .subtract(const Duration(hours: 2))
          .add(const Duration(days: 3)),
    ),
  };

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
  Future<List<Mission>> missions() async => [
    ...?_requestedMissions[_activePhone],
    if (_activePhone == _samplePhone) ..._missions,
  ];

  @override
  Future<List<Movement>> movements() async =>
      _activePhone == _samplePhone ? List.of(_movements) : [];

  @override
  Future<Mission> mission(int id) async =>
      (await missions()).firstWhere((m) => m.id == id);

  /// Fictif : « Peinture » et « Déménagement » n'existent pas encore, ils
  /// montrent seulement comment un service tout juste approuvé apparaît.
  @override
  Future<List<CatalogService>> serviceCatalog() async => [
    CatalogService(
      id: 'plomberie',
      name: 'Plomberie',
      service: Service.plomberie,
      color: 0xFF0350E6,
      lastRequested: _activePhone == _samplePhone
          ? _now.subtract(const Duration(days: 2))
          : null,
    ),
    CatalogService(
      id: 'nettoyage',
      name: 'Nettoyage',
      service: Service.nettoyage,
      color: 0xFF1E8A4C,
      lastRequested: _activePhone == _samplePhone
          ? _now.subtract(const Duration(days: 6))
          : null,
    ),
    const CatalogService(
      id: 'electricite',
      name: 'Électricité',
      service: Service.electricite,
      color: 0xFFC98200,
      recommended: true,
    ),
    const CatalogService(
      id: 'climatisation',
      name: 'Climatisation',
      service: Service.climatisation,
      color: 0xFF0A84D6,
    ),
    const CatalogService(
      id: 'informatique',
      name: 'Informatique',
      service: Service.informatique,
      color: 0xFF021937,
    ),
    const CatalogService(
      id: 'peinture',
      name: 'Peinture',
      translations: {'en': 'Painting', 'ln': 'Kopakola langi'},
      glyph: 'svcPeinture',
      color: 0xFFB4531A,
      isNew: true,
    ),
    const CatalogService(
      id: 'coiffure',
      name: 'Coiffure',
      service: Service.coiffure,
      color: 0xFFC2416B,
    ),
    const CatalogService(
      id: 'graphisme',
      name: 'Graphisme',
      service: Service.graphisme,
      color: 0xFF494C95,
    ),
    const CatalogService(
      id: 'jardinage',
      name: 'Jardinage',
      service: Service.jardinage,
      color: 0xFF4F8A10,
    ),
    const CatalogService(
      id: 'demenagement',
      name: 'Déménagement',
      translations: {'en': 'Moving', 'ln': 'Kokende kofanda esika mosusu'},
      glyph: 'svcDemenagement',
      color: 0xFF2B6CB0,
      isNew: true,
    ),
  ];

  /// Aperçu : la demande n'est envoyée nulle part.
  @override
  Future<void> sendFreeRequest(String title, String text) async {}

  @override
  Future<void> requestService({
    required String serviceId,
    required String commune,
    required String description,
  }) async {
    final phone = _activePhone;
    final catalog = await serviceCatalog();
    final service = catalog.firstWhere((service) => service.id == serviceId);
    final detail = description.trim();
    if (!serviceRequestCommunes.contains(commune) ||
        detail.length < 10 ||
        detail.length > 500) {
      throw ArgumentError('Invalid service request');
    }
    final requests = _requestedMissions.putIfAbsent(phone, () => []);
    requests.insert(
      0,
      Mission(
        id: _nextRequestId++,
        service: service.service ?? Service.autre,
        catalogService: service,
        commune: commune,
        status: MissionStatus.pending,
        payment: PaymentState.none,
        detail: detail,
        when: _now,
      ),
    );
  }

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

  @override
  Future<Dispute?> dispute(int missionId) async => _disputes[missionId];

  @override
  Future<Dispute> reportProblem(
    int missionId,
    DisputeReason reason,
    String text,
  ) async {
    final mission = await this.mission(missionId);
    final open = const [
      MissionStatus.confirmed,
      MissionStatus.inProgress,
      MissionStatus.awaitingConfirmation,
    ].contains(mission.status);
    if (!open || mission.payment != PaymentState.secured) {
      throw StateError('Plus de signalement possible sur cette mission.');
    }
    final dispute = Dispute(
      missionId: missionId,
      reason: reason,
      text: text.trim(),
      photos: 0,
      openedAt: DateTime.now(),
    );
    _disputes[missionId] = dispute;
    _replace(
      mission.copyWith(
        status: MissionStatus.disputed,
        payment: PaymentState.blocked,
      ),
    );
    return dispute;
  }

  // --- Espace prestataire (fictif) ---

  bool _inService = true;

  /// Code de présence de la cliente dans l'aperçu (sur le vrai serveur, il
  /// n'est donné qu'au client et n'est jamais enregistré).
  static const demoPresenceCode = '2580';

  DateTime _nextDay(int weekday, int hour) {
    final days = (weekday - _now.weekday + 7) % 7;
    final day = _now.add(Duration(days: days == 0 ? 7 : days));
    return DateTime(day.year, day.month, day.day, hour);
  }

  late final List<ProviderRequest> _requests = [
    ProviderRequest(
      missionId: 71,
      service: Service.nettoyage,
      commune: 'Limete',
      summary: 'Samedi matin · 3 pièces',
      description:
          'Appartement de 3 pièces, cuisine et salle de bain comprises. '
          'Produits à apporter.',
      wanted: 'Samedi matin',
      photos: 3,
      receivedAt: _now.subtract(const Duration(minutes: 3)),
      slotChoices: [
        _nextDay(DateTime.saturday, 8),
        _nextDay(DateTime.saturday, 9),
        _nextDay(DateTime.saturday, 10),
      ],
    ),
    ProviderRequest(
      missionId: 72,
      service: Service.jardinage,
      commune: 'Ngaliema',
      summary: 'Dimanche · petit jardin',
      description: 'Petit jardin devant la maison : tondre et tailler la haie.',
      wanted: 'Dimanche',
      photos: 1,
      receivedAt: _now.subtract(const Duration(minutes: 12)),
      slotChoices: [
        _nextDay(DateTime.sunday, 9),
        _nextDay(DateTime.sunday, 14),
      ],
    ),
  ];

  late final List<ProviderJob> _jobs = [
    ProviderJob(
      missionId: 61,
      service: Service.nettoyage,
      commune: 'Limete',
      clientName: 'Esther M.',
      clientInitials: 'EM',
      clientColor: 0xFFC2416B,
      place: "Limete, 7e rue · près de l'école",
      amount: const Money(25000, Currency.cdf),
      sharing: true,
      steps: {
        ProviderStep.clientPaid: _now.subtract(const Duration(minutes: 40)),
        ProviderStep.leftHome: _now.subtract(const Duration(minutes: 12)),
      },
    ),
  ];

  @override
  Future<ProviderHome> providerHome() async => ProviderHome(
    inService: _inService,
    communes: const ['Limete', 'Gombe'],
    available: const Money(120000, Currency.cdf),
    secured: _jobs
        .where((j) => !j.steps.containsKey(ProviderStep.finished))
        .fold(
          const Money(0, Currency.cdf),
          (sum, j) => j.amount.currency == Currency.cdf
              ? Money(sum.minorUnits + j.amount.minorUnits, Currency.cdf)
              : sum,
        ),
    requests: List.of(_requests),
    jobs: List.of(_jobs),
  );

  @override
  Future<void> setInService(bool value) async => _inService = value;

  @override
  Future<ProviderRequest> providerRequest(int missionId) async =>
      _requests.firstWhere((r) => r.missionId == missionId);

  @override
  Future<void> sendQuote(int missionId, Money price, DateTime slot) async {
    final i = _requests.indexWhere((r) => r.missionId == missionId);
    if (i < 0) throw StateError('mission_not_open');
    final request = _requests[i];
    if (request.quoted) throw StateError('quote_already_sent');
    if (price.minorUnits <= 0) throw ArgumentError('price_must_be_positive');
    _requests[i] = ProviderRequest(
      missionId: request.missionId,
      service: request.service,
      commune: request.commune,
      summary: request.summary,
      description: request.description,
      wanted: request.wanted,
      photos: request.photos,
      receivedAt: request.receivedAt,
      slotChoices: request.slotChoices,
      quoted: true,
    );
  }

  @override
  Future<ProviderJob> providerJob(int missionId) async =>
      _jobs.firstWhere((j) => j.missionId == missionId);

  ProviderJob _saveJob(ProviderJob job) {
    final i = _jobs.indexWhere((j) => j.missionId == job.missionId);
    _jobs[i] = job;
    return job;
  }

  @override
  Future<ProviderJob> setSharing(int missionId, bool value) async =>
      _saveJob((await providerJob(missionId)).copyWith(sharing: value));

  @override
  Future<ProviderJob> leaveForJob(int missionId) async {
    final job = await providerJob(missionId);
    if (job.steps.containsKey(ProviderStep.leftHome)) return job;
    return _saveJob(
      job.copyWith(
        steps: {...job.steps, ProviderStep.leftHome: DateTime.now()},
      ),
    );
  }

  @override
  Future<ProviderJob> signalArrival(int missionId) async {
    final job = await providerJob(missionId);
    if (!job.steps.containsKey(ProviderStep.leftHome)) {
      throw StateError('not_on_the_way');
    }
    return _saveJob(job.copyWith(arrivalSignaled: true));
  }

  @override
  Future<PresenceResult> enterPresenceCode(int missionId, String code) async {
    final job = await providerJob(missionId);
    if (job.steps.containsKey(ProviderStep.arrived)) {
      return PresenceResult.confirmed;
    }
    if (!job.arrivalSignaled) throw StateError('arrival_not_signaled');
    if (job.codeAttemptsLeft <= 0) return PresenceResult.locked;
    if (code.trim() != demoPresenceCode) {
      final left = job.codeAttemptsLeft - 1;
      _saveJob(job.copyWith(codeAttemptsLeft: left));
      return left == 0 ? PresenceResult.locked : PresenceResult.wrongCode;
    }
    _saveJob(
      job.copyWith(steps: {...job.steps, ProviderStep.arrived: DateTime.now()}),
    );
    return PresenceResult.confirmed;
  }

  @override
  Future<ProviderJob> finishJob(int missionId) async {
    final job = await providerJob(missionId);
    if (!job.steps.containsKey(ProviderStep.arrived)) {
      throw StateError('arrival_not_confirmed');
    }
    if (job.steps.containsKey(ProviderStep.finished)) return job;
    return _saveJob(
      job.copyWith(
        steps: {...job.steps, ProviderStep.finished: DateTime.now()},
      ),
    );
  }

  static String _label(Service service) => switch (service) {
    Service.nettoyage => 'Nettoyage',
    Service.plomberie => 'Plomberie',
    Service.electricite => 'Électricité',
    Service.coiffure => 'Coiffure',
    Service.climatisation => 'Climatisation',
    Service.jardinage => 'Jardinage',
    _ => service.name,
  };
}
