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
      'Nous vous mettons en relation avec des professionnels de confiance';

  @override
  String get start => 'Commencer';

  @override
  String get haveAccount => 'J\'ai déjà un compte';

  @override
  String get yourNumber => 'Votre numéro';

  @override
  String get yourNumberIntro =>
      'Nous vous envoyons un code pour vérifier que c\'est bien vous.';

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
  String get pickServiceHint => 'Choisissez, nous nous occupons du reste.';

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
      'Votre argent reste sécurisé par Nexis Hub jusqu\'à ce que vous confirmiez que c\'est fait.';

  @override
  String get payTitle => 'Payer';

  @override
  String get payWith => 'Payer avec';

  @override
  String get addNumber => 'Ajouter un numéro';

  @override
  String paySecuredNote(String name) {
    return 'Sécurisé par Nexis Hub : $name reçoit l\'argent quand vous confirmez que c\'est fait.';
  }

  @override
  String payAmount(String amount) {
    return 'Payer $amount';
  }

  @override
  String get pendingTitle => 'Validez sur votre téléphone';

  @override
  String pendingText(String operator, String amount) {
    return '$operator vous envoie une demande de $amount. Tapez votre code secret Mobile Money pour l\'accepter.';
  }

  @override
  String pendingSent(String operator) {
    return 'Demande envoyée à $operator';
  }

  @override
  String get pendingWaiting => 'En attente de confirmation';

  @override
  String get pendingWithin => 'Vous avez 5 minutes';

  @override
  String get pendingSecured => 'Argent sécurisé par Nexis Hub';

  @override
  String pendingNotify(String name) {
    return 'Nous prévenons $name tout de suite';
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
    return 'Vous confirmez, $name reçoit l\'argent';
  }

  @override
  String get confirmAction => 'Confirmer';

  @override
  String confirmQuestion(String name) {
    return '$name a terminé.\nC\'est bien fait ?';
  }

  @override
  String confirmText(String name) {
    return 'Quand vous confirmez, Nexis Hub verse l\'argent sécurisé à $name.';
  }

  @override
  String paidTo(String name) {
    return 'Versé à $name';
  }

  @override
  String get amountFixed => 'Montant fixé par Nexis Hub au paiement';

  @override
  String get report48h =>
      'Un souci ? Vous avez 48 h pour le signaler. L\'argent reste alors bloqué le temps que nous regardions avec vous deux.';

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
  String get reportHint => 'Racontez en quelques mots ce qui ne va pas.';

  @override
  String get addPhoto => 'Ajouter une photo';

  @override
  String reportFrozen(String amount) {
    return 'Les $amount sont bloqués le temps que nous regardions avec vous deux. Personne ne peut y toucher.';
  }

  @override
  String get sendReport => 'Envoyer le signalement';

  @override
  String get reportFailed =>
      'Le signalement n\'est pas parti. Réessayez dans un instant.';

  @override
  String get disputeTitle => 'Litige';

  @override
  String get nobodyTouches => 'Personne ne peut y toucher';

  @override
  String get youReported => 'Vous avez signalé';

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
  String get nexisLookingSub => 'Réponse sous 48 h · nous pouvons vous appeler';

  @override
  String get decisionStep => 'Décision et argent';

  @override
  String get decisionStepSub => 'Versé, remboursé ou partagé';

  @override
  String settleHint(String name) {
    return 'Vous pouvez encore vous arranger avec $name. Si vous êtes d\'accord, dites-le ici et nous clôturons le litige.';
  }

  @override
  String get writeNexis => 'Écrire à Nexis Hub';

  @override
  String get weSettled => 'Nous nous sommes arrangés';

  @override
  String get disputeOver => 'Litige terminé';

  @override
  String get outcomeRefundTitle => 'Nous vous remboursons';

  @override
  String outcomeRefundText(String name) {
    return 'Après avoir regardé le dossier et parlé avec $name, Nexis Hub a décidé de vous rembourser. L\'argent arrive dans votre portefeuille dans 3 jours si personne ne conteste.';
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
    return 'Après avoir regardé le dossier avec vous deux, Nexis Hub a décidé de partager l\'argent entre vous et $name. Votre part arrive dans votre portefeuille dans 3 jours si personne ne conteste.';
  }

  @override
  String get toRefundYou => 'À vous rembourser';

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
          'Pas d\'accord ? Vous avez $count jours pour demander à revoir la décision. L\'argent reste bloqué pendant ce temps.',
      one: 'Pas d\'accord ? Vous avez encore 1 jour pour demander à revoir la décision. L\'argent reste bloqué pendant ce temps.',
    );
    return '$_temp0';
  }

  @override
  String get seeWallet => 'Voir mon portefeuille';

  @override
  String get inService => 'En service';

  @override
  String get offService => 'Hors service';

  @override
  String inServiceSub(String communes) {
    return 'Vous recevez les demandes de $communes';
  }

  @override
  String get offServiceSub => 'Vous ne recevez pas de nouvelles demandes';

  @override
  String get offServiceHint =>
      'Active « En service » pour recevoir les demandes des clients.';

  @override
  String andList(String head, String last) {
    return '$head et $last';
  }

  @override
  String securedUntilConfirm(String amount) {
    return '$amount sécurisés, versés quand le client confirme';
  }

  @override
  String get newRequests => 'Nouvelles demandes';

  @override
  String get noRequests => 'Pas de nouvelle demande pour l\'instant.';

  @override
  String get jobsInProgress => 'Missions en cours';

  @override
  String get newPill => 'Nouveau';

  @override
  String minutesAgo(int count) {
    return '$count min';
  }

  @override
  String hoursAgo(int count) {
    return '$count h';
  }

  @override
  String get quoteSentPill => 'Devis envoyé';

  @override
  String get sendAQuote => 'Envoyer un devis';

  @override
  String get sendTheQuote => 'Envoyer le devis';

  @override
  String get yourPrice => 'Votre prix';

  @override
  String get priceAsked => 'Montant demandé au client';

  @override
  String get changeCurrency => 'Changer de devise';

  @override
  String get yourSlot => 'Votre créneau';

  @override
  String get otherSlot => 'Autre';

  @override
  String get quoteSentToast =>
      'Devis envoyé. Vous serez prévenu si le client le choisit.';

  @override
  String get quoteFailed =>
      'Le devis n\'est pas parti. Réessayez dans un instant.';

  @override
  String get actionFailed =>
      'Cela n\'a pas fonctionné. Réessayez dans un instant.';

  @override
  String get jobTitle => 'Mission';

  @override
  String get jobToStart => 'Payé, à vous de partir';

  @override
  String get jobOnTheWay => 'En route';

  @override
  String jobArrivalPending(String name) {
    return 'Arrivée à confirmer par $name';
  }

  @override
  String get jobOnSite => 'Sur place';

  @override
  String jobWaitingClient(String name) {
    return 'Terminé, $name doit confirmer';
  }

  @override
  String get shareLocation => 'Partager ma position';

  @override
  String shareLocationSub(String name) {
    return '$name voit la distance jusqu\'à votre arrivée';
  }

  @override
  String get pStepPaid => 'Client a payé';

  @override
  String get pStepLeft => 'Je suis parti';

  @override
  String get pStepArrive => 'J\'arrive sur place';

  @override
  String get pStepOnSite => 'Je suis sur place';

  @override
  String get pStepDone => 'J\'ai terminé';

  @override
  String get btnLeave => 'Je pars';

  @override
  String get btnArrived => 'Je suis arrivé';

  @override
  String get btnFinished => 'J\'ai terminé';

  @override
  String callClient(String name) {
    return 'Appeler $name';
  }

  @override
  String arrivalWaiting(String name) {
    return '$name doit confirmer votre arrivée sur son téléphone. Vous pouvez aussi taper son code de présence.';
  }

  @override
  String arrivalWaitingSub(String name) {
    return 'En attente de $name';
  }

  @override
  String get arrivalConfirmed => 'Arrivée confirmée';

  @override
  String get presenceCode => 'Code de présence du client';

  @override
  String get confirmCode => 'Valider';

  @override
  String wrongCode(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Code incorrect. Encore $count essais.',
      one: 'Code incorrect. Encore 1 essai.',
    );
    return '$_temp0';
  }

  @override
  String codeLocked(String name) {
    return 'Trop d\'essais. Seul $name peut maintenant confirmer votre arrivée.';
  }

  @override
  String finishedNote(String name) {
    return '$name a 48 h pour confirmer ou signaler un problème. Sans réponse, l\'argent vous est versé au bout de 48 h.';
  }

  @override
  String get numberPrivate =>
      'Votre numéro n\'est jamais montré aux prestataires.';

  @override
  String get numberUnknownPrefix =>
      'Ce numéro ne correspond à aucun opérateur de RDC.';

  @override
  String get smsSub => 'Un SMS avec le code';

  @override
  String get receiveOtherWay => 'Recevoir le code autrement';

  @override
  String codeSentBySms(String phone) {
    return 'Envoyé par SMS au $phone';
  }

  @override
  String get noCodeChannel =>
      'Aucun canal n\'est disponible pour le moment. Réessayez dans un instant.';
}
