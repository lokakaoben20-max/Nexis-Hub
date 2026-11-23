import 'money.dart';

/// Les neuf services de Nexis (mêmes clés que le serveur et le bot).
enum Service {
  plomberie,
  electricite,
  climatisation,
  informatique,
  graphisme,
  coiffure,
  nettoyage,
  jardinage,
  autre,
}

/// États d'une mission vus par le client (mêmes valeurs que le serveur).
enum MissionStatus {
  pending,
  quoted,
  confirmed,
  inProgress,
  awaitingConfirmation,
  completed,
  cancelled,
  disputed,
}

/// Les six états de l'argent de la charte.
enum PaymentState { none, secured, released, refunded, blocked, available }

class Mission {
  const Mission({
    required this.id,
    required this.service,
    required this.commune,
    required this.status,
    required this.payment,
    this.amount,
    this.providerName,
    this.quotesCount = 0,
    this.when,
    this.rated = false,
    this.detail,
    this.wanted,
    this.chosen,
    this.distanceKm,
    this.steps = const {},
    this.providerRating,
    this.providerReviews,
  });

  final int id;
  final Service service;
  final String commune;
  final MissionStatus status;
  final PaymentState payment;
  final Money? amount;
  final String? providerName;
  final int quotesCount;
  final DateTime? when;

  /// Le client a déjà noté la prestation (étoile sur la carte).
  final bool rated;

  /// Précisions écrites par le client (« 3 pièces ») et moment souhaité
  /// (« Samedi matin »), tels qu'il les a saisis.
  final String? detail;
  final String? wanted;

  /// Le devis choisi et payé (prestataire, prix, créneau).
  final Quote? chosen;

  /// Distance du prestataire en route, seulement s'il partage sa position.
  final double? distanceKm;

  /// Heure de chaque étape franchie du suivi.
  final Map<TrackStep, DateTime> steps;

  /// Note et nombre d'avis du prestataire, tels que le serveur les donne
  /// (jamais calculés dans l'app).
  final double? providerRating;
  final int? providerReviews;

  double? get rating => chosen?.rating ?? providerRating;
  int? get reviews => chosen?.reviews ?? providerReviews;

  Mission copyWith({
    MissionStatus? status,
    PaymentState? payment,
    Money? amount,
    String? providerName,
    Quote? chosen,
    Map<TrackStep, DateTime>? steps,
  }) => Mission(
    id: id,
    service: service,
    commune: commune,
    status: status ?? this.status,
    payment: payment ?? this.payment,
    amount: amount ?? this.amount,
    providerName: providerName ?? this.providerName,
    quotesCount: quotesCount,
    when: when,
    rated: rated,
    detail: detail,
    wanted: wanted,
    chosen: chosen ?? this.chosen,
    distanceKm: distanceKm,
    steps: steps ?? this.steps,
    providerRating: providerRating,
    providerReviews: providerReviews,
  );

  bool get isActive => const [
    MissionStatus.pending,
    MissionStatus.quoted,
    MissionStatus.confirmed,
    MissionStatus.inProgress,
    MissionStatus.awaitingConfirmation,
    MissionStatus.disputed,
  ].contains(status);

  String get reference => 'NXH-${id.toString().padLeft(4, '0')}';
}

class Wallet {
  const Wallet({required this.available, required this.secured});

  /// Solde disponible, par devise.
  final Map<Currency, Money> available;

  /// Argent payé pour des missions en cours, protégé par Nexis.
  final Map<Currency, Money> secured;
}

enum MovementKind { payment, refund, release, deposit, withdrawal }

class Movement {
  const Movement({
    required this.kind,
    required this.label,
    required this.amount,
    required this.when,
    required this.state,
  });

  final MovementKind kind;
  final String label;
  final Money amount;
  final DateTime when;
  final PaymentState state;
}

class Profile {
  const Profile({
    required this.firstName,
    required this.lastName,
    required this.phone,
    required this.commune,
    required this.isProvider,
    this.termsVersion,
  });

  /// Date de la version des conditions d'utilisation en vigueur et
  /// acceptée (donnée du serveur).
  final DateTime? termsVersion;

  final String firstName;
  final String lastName;
  final String phone;
  final String commune;
  final bool isProvider;

  String get initials =>
      '${firstName.isEmpty ? '' : firstName[0]}${lastName.isEmpty ? '' : lastName[0]}'
          .toUpperCase();
}

/// Les étapes du suivi d'une mission payée (maquette 6).
enum TrackStep { paid, onTheWay, onSite, workDone, confirmed }

/// Un devis reçu : le prix et le créneau viennent du serveur tels quels.
class Quote {
  const Quote({
    required this.id,
    required this.providerName,
    required this.initials,
    required this.avatarColor,
    required this.rating,
    required this.reviews,
    required this.price,
    required this.slot,
  });

  final int id;
  final String providerName;
  final String initials;
  final int avatarColor;
  final double rating;
  final int reviews;
  final Money price;
  final DateTime slot;

  /// Prénom seul, pour « Choisir Prisca ».
  String get firstName => providerName.split(' ').first;
}

/// Les trois opérateurs Mobile Money de la maquette.
enum MobileOperator { mpesa, orange, airtel }

/// Un numéro Mobile Money du client (masqué), ou rien d'enregistré.
class PayAccount {
  const PayAccount(this.operator, this.maskedNumber);

  final MobileOperator operator;
  final String? maskedNumber;
}

/// Ce qui s'est mal passé, choisi par le client (maquette 25).
enum DisputeReason { notFinished, badWork, noShow, other }

/// Les trois fins possibles d'un litige, décidées par Nexis Hub.
enum DisputeOutcome { release, refund, split }

/// Un litige : l'argent de la mission reste bloqué jusqu'à la décision,
/// puis encore 3 jours (le temps de contester). Les montants de la
/// décision sont calculés par le serveur, l'app ne fait que les montrer.
class Dispute {
  const Dispute({
    required this.missionId,
    required this.reason,
    required this.text,
    required this.photos,
    required this.openedAt,
    this.providerReply,
    this.providerRepliedAt,
    this.outcome,
    this.decidedAt,
    this.clientAmount,
    this.providerAmount,
    this.contestUntil,
  });

  final int missionId;
  final DisputeReason reason;
  final String text;
  final int photos;
  final DateTime openedAt;
  final String? providerReply;
  final DateTime? providerRepliedAt;
  final DisputeOutcome? outcome;
  final DateTime? decidedAt;
  final Money? clientAmount;
  final Money? providerAmount;
  final DateTime? contestUntil;

  bool get decided => outcome != null;
}

/// Une demande de client reçue par le prestataire, à laquelle il peut
/// répondre par un devis (maquette 11 et 12).
class ProviderRequest {
  const ProviderRequest({
    required this.missionId,
    required this.service,
    required this.commune,
    required this.summary,
    required this.description,
    required this.wanted,
    required this.photos,
    required this.receivedAt,
    required this.slotChoices,
    this.quoted = false,
  });

  final int missionId;
  final Service service;
  final String commune;

  /// « Samedi matin · 3 pièces ».
  final String summary;
  final String description;

  /// Le moment souhaité par le client, en mots (« Samedi matin »).
  final String wanted;
  final int photos;
  final DateTime receivedAt;

  /// Créneaux proposés d'après le souhait du client ; « Autre » en plus.
  final List<DateTime> slotChoices;

  /// Le devis est déjà parti : le client le compare aux autres.
  final bool quoted;
}

/// Les étapes d'une mission vue par le prestataire (maquette 13).
enum ProviderStep { clientPaid, leftHome, arrived, finished }

/// Une mission payée, du côté du prestataire.
class ProviderJob {
  const ProviderJob({
    required this.missionId,
    required this.service,
    required this.commune,
    required this.clientName,
    required this.clientInitials,
    required this.clientColor,
    required this.place,
    required this.amount,
    required this.steps,
    this.sharing = false,
    this.arrivalSignaled = false,
    this.codeAttemptsLeft = 5,
  });

  final int missionId;
  final Service service;
  final String commune;
  final String clientName;
  final String clientInitials;
  final int clientColor;

  /// Le lieu exact, donné seulement une fois la mission payée.
  final String place;

  /// L'argent sécurisé du client pour cette mission.
  final Money amount;
  final Map<ProviderStep, DateTime> steps;
  final bool sharing;

  /// « Je suis arrivé » envoyé ; l'arrivée attend la preuve du client
  /// (son appui ou son code de présence).
  final bool arrivalSignaled;
  final int codeAttemptsLeft;

  String get clientFirstName => clientName.split(' ').first;

  ProviderJob copyWith({
    Map<ProviderStep, DateTime>? steps,
    bool? sharing,
    bool? arrivalSignaled,
    int? codeAttemptsLeft,
  }) => ProviderJob(
    missionId: missionId,
    service: service,
    commune: commune,
    clientName: clientName,
    clientInitials: clientInitials,
    clientColor: clientColor,
    place: place,
    amount: amount,
    steps: steps ?? this.steps,
    sharing: sharing ?? this.sharing,
    arrivalSignaled: arrivalSignaled ?? this.arrivalSignaled,
    codeAttemptsLeft: codeAttemptsLeft ?? this.codeAttemptsLeft,
  );
}

/// L'accueil prestataire : en service ou non, l'argent, les demandes.
class ProviderHome {
  const ProviderHome({
    required this.inService,
    required this.communes,
    required this.available,
    required this.secured,
    required this.requests,
    required this.jobs,
  });

  final bool inService;
  final List<String> communes;
  final Money available;
  final Money secured;
  final List<ProviderRequest> requests;
  final List<ProviderJob> jobs;
}

/// Réponse au code de présence tapé par le prestataire.
enum PresenceResult { confirmed, wrongCode, locked }

/// Un service du catalogue tel que le serveur le publie : les services
/// existants, plus ceux que l'équipe vient d'approuver. L'app ne décide
/// ni de la liste, ni de qui est « nouveau », ni de l'ordre.
class CatalogService {
  const CatalogService({
    required this.id,
    required this.name,
    required this.color,
    this.translations = const {},
    this.service,
    this.glyph,
    this.isNew = false,
    this.lastRequested,
    this.recommended = false,
  });

  final String id;
  final String name;
  final int color;
  final Map<String, String> translations;

  /// Service connu de l'app (icône de la police Nexis) ; sinon `glyph`.
  final Service? service;
  final String? glyph;

  /// Ajouté récemment : le serveur fixe la durée de la mention « Nouveau ».
  final bool isNew;
  final DateTime? lastRequested;
  final bool recommended;
}
