// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for French (`fr`).
class AppLocalizationsFr extends AppLocalizations {
  AppLocalizationsFr([String locale = 'fr']) : super(locale);

  @override
  String get previewBanner => 'Aperçu · données fictives';

  @override
  String get slogan => 'Là où la confiance rencontre le service.';

  @override
  String get welcomeIntro =>
      'Plomberie, électricité, nettoyage et plus encore à Kinshasa. Ton argent reste sécurisé jusqu\'à ce que tu confirmes.';

  @override
  String get start => 'Commencer';

  @override
  String get haveAccount => 'J\'ai déjà un compte';

  @override
  String get yourNumber => 'Ton numéro';

  @override
  String get yourNumberIntro =>
      'On t\'envoie un code pour vérifier que c\'est bien toi.';

  @override
  String get receiveCodeBy => 'Recevoir le code par';

  @override
  String get whatsappSub => 'Le code arrive en quelques secondes';

  @override
  String get telegramSub => 'Avec le bot Nexis Hub';

  @override
  String get receiveCode => 'Recevoir le code';

  @override
  String get theCode => 'Le code';

  @override
  String codeSentTo(String channel, String phone) {
    return 'Envoyé sur $channel au $phone';
  }

  @override
  String get demoCodeHint => 'Aperçu : tape n\'importe quels 6 chiffres.';

  @override
  String get welcomeBack => 'Bon retour';

  @override
  String hello(String name) {
    return 'Mbote, $name';
  }

  @override
  String get myWallets => 'Mes portefeuilles';

  @override
  String get available => 'Disponible';

  @override
  String securedAmount(String amount) {
    return '$amount sécurisés';
  }

  @override
  String get hideAmounts => 'Masquer les montants';

  @override
  String get showAmounts => 'Afficher les montants';

  @override
  String get actionServices => 'Services';

  @override
  String get actionDeposit => 'Dépôt';

  @override
  String get actionWithdraw => 'Retrait';

  @override
  String get actionHistory => 'Historique';

  @override
  String get actionMore => 'Plus';

  @override
  String get lastServices => 'Dernières prestations';

  @override
  String get tabDone => 'Terminées';

  @override
  String get tabOngoing => 'En cours';

  @override
  String get navHome => 'Accueil';

  @override
  String get navMissions => 'Missions';

  @override
  String get navWallet => 'Portefeuille';

  @override
  String get navProfile => 'Profil';

  @override
  String get requestService => 'Demander un service';

  @override
  String get whichService => 'Quel service ?';

  @override
  String get notInList => 'Mon besoin n\'est pas dans la liste';

  @override
  String get myMissions => 'Mes missions';

  @override
  String get noMissions => 'Rien ici pour l\'instant.';

  @override
  String get statusPending => 'En attente de devis';

  @override
  String statusQuoted(int count) {
    return '$count devis reçus';
  }

  @override
  String get statusConfirmed => 'Prestataire choisi';

  @override
  String statusInProgress(String name) {
    return '$name est en route';
  }

  @override
  String get statusAwaiting => 'À confirmer';

  @override
  String get statusCompleted => 'Terminée';

  @override
  String get statusCancelled => 'Annulée';

  @override
  String get statusDisputed => 'Litige en cours';

  @override
  String get compareQuotes => 'Comparer les devis';

  @override
  String get follow => 'Suivre';

  @override
  String get paySecured => 'Sécurisé par Nexis Hub';

  @override
  String get payReleased => 'Versé au prestataire';

  @override
  String get payRefunded => 'Remboursé';

  @override
  String get payBlocked => 'Bloqué (litige)';

  @override
  String get payAvailable => 'Disponible';

  @override
  String get movements => 'Mouvements';

  @override
  String get seeAll => 'Tout voir';

  @override
  String get today => 'Aujourd\'hui';

  @override
  String get yesterday => 'Hier';

  @override
  String get comingSoon => 'Bientôt dans l\'app';

  @override
  String get comingSoonText =>
      'Cet écran arrive dans une prochaine version de l\'aperçu.';

  @override
  String get ok => 'Compris';

  @override
  String get phone => 'Téléphone';

  @override
  String get commune => 'Commune';

  @override
  String get language => 'Langue';

  @override
  String get myDevices => 'Mes appareils';

  @override
  String get help => 'Aide';

  @override
  String get becomeProvider => 'Devenir prestataire';

  @override
  String get becomeProviderSub => 'Le même compte, le même portefeuille';

  @override
  String get signOut => 'Se déconnecter';

  @override
  String get clientBadge => 'Client';

  @override
  String get back => 'Retour';

  @override
  String get editProfile => 'Modifier';

  @override
  String get pickServiceHint => 'Choisis, on s\'occupe du reste.';

  @override
  String get otherNeed => 'Autre';

  @override
  String get close => 'Fermer';
}
