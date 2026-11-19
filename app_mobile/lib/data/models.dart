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
