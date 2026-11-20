// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for French (`fr`).
class AppLocalizationsFr extends AppLocalizations {
  AppLocalizationsFr([String locale = 'fr']) : super(locale);

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
  String get welcomeBack => 'Bon retour';

  @override
  String hello(String name) {
    return 'Bonjour, $name';
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
  String get comingSoonText => 'Cet écran arrive dans une prochaine version.';

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

  @override
  String quotesPill(int count) {
    return '$count devis';
  }

  @override
  String get waitingPill => 'En attente';

  @override
  String legalText(String terms, String privacy) {
    return 'En continuant, tu acceptes les $terms et la $privacy.';
  }

  @override
  String get legalTerms => 'Conditions d\'utilisation';

  @override
  String get legalPrivacy => 'Politique de confidentialité';

  @override
  String get notReceived => 'Pas reçu ?';

  @override
  String resendIn(String time) {
    return 'Renvoyer dans $time';
  }

  @override
  String get resendNow => 'Renvoyer le code';

  @override
  String receiveInstead(String channel) {
    return 'Recevoir plutôt par $channel';
  }

  @override
  String get myInfo => 'Mes informations';

  @override
  String get myInfoSub => 'Nom, photo, commune';

  @override
  String devicesCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count appareils connectés',
      one: '1 appareil connecté',
    );
    return '$_temp0';
  }

  @override
  String get helpDisputes => 'Aide et litiges';

  @override
  String get helpDisputesSub => 'Un souci sur une mission';

  @override
  String get spaceClient => 'Client';

  @override
  String get spaceProvider => 'Prestataire';

  @override
  String get bestRated => 'Le mieux noté';

  @override
  String chooseProvider(String name) {
    return 'Choisir $name';
  }

  @override
  String get securedUntilDone =>
      'Ton argent reste sécurisé par Nexis Hub jusqu\'à ce que tu confirmes que c\'est fait.';

  @override
  String get payTitle => 'Payer';

  @override
  String get payWith => 'Payer avec';

  @override
  String get addNumber => 'Ajouter un numéro';

  @override
  String paySecuredNote(String name) {
    return 'Sécurisé par Nexis Hub : $name reçoit l\'argent quand tu confirmes que c\'est fait.';
  }

  @override
  String payAmount(String amount) {
    return 'Payer $amount';
  }

  @override
  String get pendingTitle => 'Valide sur ton téléphone';

  @override
  String pendingText(String operator, String amount) {
    return '$operator t\'envoie une demande de $amount. Tape ton code secret Mobile Money pour l\'accepter.';
  }

  @override
  String pendingSent(String operator) {
    return 'Demande envoyée à $operator';
  }

  @override
  String get pendingWaiting => 'En attente de confirmation';

  @override
  String get pendingWithin => 'Tu as 5 minutes';

  @override
  String get pendingSecured => 'Argent sécurisé par Nexis Hub';

  @override
  String pendingNotify(String name) {
    return 'On prévient $name tout de suite';
  }

  @override
  String get nothingReceived => 'Je n\'ai rien reçu';

  @override
  String get paymentTitle => 'Paiement';

  @override
  String get trackTitle => 'Suivi';

  @override
  String distanceAway(String name, String km) {
    return '$name est à $km km';
  }

  @override
  String get trackingOff => 'Suivi non activé';

  @override
  String get stepPaid => 'Payé';

  @override
  String get stepOnTheWay => 'En route';

  @override
  String get stepOnTheWaySub => 'Suivi de position activé';

  @override
  String get stepOnSite => 'Sur place';

  @override
  String get stepWorkDone => 'Travail terminé';

  @override
  String stepConfirm(String name) {
    return 'Tu confirmes, $name reçoit l\'argent';
  }

  @override
  String get confirmAction => 'Confirmer';

  @override
  String confirmQuestion(String name) {
    return '$name a terminé.\nC\'est bien fait ?';
  }

  @override
  String confirmText(String name) {
    return 'Quand tu confirmes, Nexis Hub verse l\'argent sécurisé à $name.';
  }

  @override
  String paidTo(String name) {
    return 'Versé à $name';
  }

  @override
  String get amountFixed => 'Montant fixé par Nexis Hub au paiement';

  @override
  String get report48h =>
      'Un souci ? Tu as 48 h pour le signaler. L\'argent reste alors bloqué le temps qu\'on regarde avec vous deux.';

  @override
  String get yesDone => 'Oui, c\'est fait';

  @override
  String get reportProblem => 'Signaler un problème';

  @override
  String confirmedToast(String name) {
    return 'Merci ! $name reçoit l\'argent.';
  }

  @override
  String get callLabel => 'Appeler';

  @override
  String get messageLabel => 'Écrire';

  @override
  String get whatHappened => 'Que s\'est-il passé ?';

  @override
  String get reasonNotFinished => 'Le travail n\'est pas fini';

  @override
  String get reasonBadWork => 'Le travail est mal fait';

  @override
  String get reasonNoShow => 'Le prestataire n\'est pas venu';

  @override
  String get reasonOther => 'Autre problème';

  @override
  String get reportHint => 'Raconte en quelques mots ce qui ne va pas.';

  @override
  String get addPhoto => 'Ajouter une photo';

  @override
  String reportFrozen(String amount) {
    return 'Les $amount sont bloqués le temps qu\'on regarde avec vous deux. Personne ne peut y toucher.';
  }

  @override
  String get sendReport => 'Envoyer le signalement';

  @override
  String get reportFailed =>
      'Le signalement n\'est pas parti. Réessaie dans un instant.';

  @override
  String get disputeTitle => 'Litige';

  @override
  String get nobodyTouches => 'Personne ne peut y toucher';

  @override
  String get youReported => 'Tu as signalé';

  @override
  String photosCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count photos',
      one: '1 photo',
      zero: 'sans photo',
    );
    return '$_temp0';
  }

  @override
  String providerReplied(String name) {
    return '$name a répondu';
  }

  @override
  String get nexisLooking => 'Nexis Hub regarde';

  @override
  String get nexisLookingSub => 'Réponse sous 48 h · on peut vous appeler';

  @override
  String get decisionStep => 'Décision et argent';

  @override
  String get decisionStepSub => 'Versé, remboursé ou partagé';

  @override
  String settleHint(String name) {
    return 'Tu peux encore t\'arranger avec $name. Si vous êtes d\'accord, dis-le ici et on clôt le litige.';
  }

  @override
  String get writeNexis => 'Écrire à Nexis Hub';

  @override
  String get weSettled => 'On s\'est arrangés';

  @override
  String get disputeOver => 'Litige terminé';

  @override
  String get outcomeRefundTitle => 'On te rembourse';

  @override
  String outcomeRefundText(String name) {
    return 'Après avoir regardé le dossier et parlé avec $name, Nexis Hub a décidé de te rembourser. L\'argent arrive dans ton portefeuille dans 3 jours si personne ne conteste.';
  }

  @override
  String outcomeReleaseTitle(String name) {
    return 'L\'argent va à $name';
  }

  @override
  String outcomeReleaseText(String name) {
    return 'Après avoir regardé le dossier avec vous deux, Nexis Hub a décidé que l\'argent revient à $name. Il part dans 3 jours si personne ne conteste.';
  }

  @override
  String get outcomeSplitTitle => 'L\'argent est partagé';

  @override
  String outcomeSplitText(String name) {
    return 'Après avoir regardé le dossier avec vous deux, Nexis Hub a décidé de partager l\'argent entre toi et $name. Ta part arrive dans ton portefeuille dans 3 jours si personne ne conteste.';
  }

  @override
  String get toRefundYou => 'À te rembourser';

  @override
  String forProvider(String name) {
    return 'Pour $name';
  }

  @override
  String blockedDaysLeft(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Bloqué (litige) · encore $count jours',
      one: 'Bloqué (litige) · encore 1 jour',
    );
    return '$_temp0';
  }

  @override
  String contestHint(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other:
          'Pas d\'accord ? Tu as $count jours pour demander à revoir la décision. L\'argent reste bloqué pendant ce temps.',
      one: 'Pas d\'accord ? Tu as encore 1 jour pour demander à revoir la décision. L\'argent reste bloqué pendant ce temps.',
    );
    return '$_temp0';
  }

  @override
  String get seeWallet => 'Voir mon portefeuille';
}
