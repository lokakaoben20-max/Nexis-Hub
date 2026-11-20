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
  );

  bool get isActive => const [
    MissionStatus.pending,
    MissionStatus.quoted,
    MissionStatus.confirmed,
    MissionStatus.inProgress,
    MissionStatus.awaitingConfirmation,
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
  });

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
