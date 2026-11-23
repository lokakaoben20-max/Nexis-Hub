import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';
import 'app_localizations_fr.dart';
import 'app_localizations_ln.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('en'),
    Locale('fr'),
    Locale('ln'),
  ];

  /// No description provided for @slogan.
  ///
  /// In fr, this message translates to:
  /// **'Là où la confiance rencontre le service.'**
  String get slogan;

  /// No description provided for @welcomeIntro.
  ///
  /// In fr, this message translates to:
  /// **'Nous vous mettons en relation avec des professionnels de confiance'**
  String get welcomeIntro;

  /// No description provided for @verifiedProvider.
  ///
  /// In fr, this message translates to:
  /// **'Prestataire vérifié'**
  String get verifiedProvider;

  /// No description provided for @start.
  ///
  /// In fr, this message translates to:
  /// **'Commencer'**
  String get start;

  /// No description provided for @haveAccount.
  ///
  /// In fr, this message translates to:
  /// **'J\'ai déjà un compte'**
  String get haveAccount;

  /// No description provided for @yourNumber.
  ///
  /// In fr, this message translates to:
  /// **'Votre numéro'**
  String get yourNumber;

  /// No description provided for @yourNumberIntro.
  ///
  /// In fr, this message translates to:
  /// **'Nous vous envoyons un code pour vérifier que c’est bien vous.'**
  String get yourNumberIntro;

  /// No description provided for @receiveCodeBy.
  ///
  /// In fr, this message translates to:
  /// **'Recevoir le code par'**
  String get receiveCodeBy;

  /// No description provided for @whatsappSub.
  ///
  /// In fr, this message translates to:
  /// **'Le code arrive en quelques secondes'**
  String get whatsappSub;

  /// No description provided for @telegramSub.
  ///
  /// In fr, this message translates to:
  /// **'Avec le bot Nexis Hub'**
  String get telegramSub;

  /// No description provided for @receiveCode.
  ///
  /// In fr, this message translates to:
  /// **'Recevoir le code'**
  String get receiveCode;

  /// No description provided for @codeSentTo.
  ///
  /// In fr, this message translates to:
  /// **'Envoyé sur {channel} au {phone}.'**
  String codeSentTo(String channel, String phone);

  /// No description provided for @welcomeBack.
  ///
  /// In fr, this message translates to:
  /// **'Bon retour'**
  String get welcomeBack;

  /// No description provided for @hello.
  ///
  /// In fr, this message translates to:
  /// **'Bonjour, {name}'**
  String hello(String name);

  /// No description provided for @myWallets.
  ///
  /// In fr, this message translates to:
  /// **'Mes portefeuilles'**
  String get myWallets;

  /// No description provided for @available.
  ///
  /// In fr, this message translates to:
  /// **'Disponible'**
  String get available;

  /// No description provided for @securedAmount.
  ///
  /// In fr, this message translates to:
  /// **'{amount} sécurisés'**
  String securedAmount(String amount);

  /// No description provided for @hideAmounts.
  ///
  /// In fr, this message translates to:
  /// **'Masquer les montants'**
  String get hideAmounts;

  /// No description provided for @showAmounts.
  ///
  /// In fr, this message translates to:
  /// **'Afficher les montants'**
  String get showAmounts;

  /// No description provided for @walletLocked.
  ///
  /// In fr, this message translates to:
  /// **'{amount} bloqués pour vos missions en cours'**
  String walletLocked(String amount);

  /// No description provided for @walletExplanation.
  ///
  /// In fr, this message translates to:
  /// **'Cet argent est versé au prestataire uniquement après confirmation du client.'**
  String get walletExplanation;

  /// No description provided for @walletInfoLabel.
  ///
  /// In fr, this message translates to:
  /// **'Pourquoi ce montant est-il bloqué ?'**
  String get walletInfoLabel;

  /// No description provided for @actionServices.
  ///
  /// In fr, this message translates to:
  /// **'Services'**
  String get actionServices;

  /// No description provided for @actionDeposit.
  ///
  /// In fr, this message translates to:
  /// **'Dépôt'**
  String get actionDeposit;

  /// No description provided for @actionWithdraw.
  ///
  /// In fr, this message translates to:
  /// **'Retrait'**
  String get actionWithdraw;

  /// No description provided for @actionHistory.
  ///
  /// In fr, this message translates to:
  /// **'Historique'**
  String get actionHistory;

  /// No description provided for @actionMore.
  ///
  /// In fr, this message translates to:
  /// **'Plus'**
  String get actionMore;

  /// No description provided for @lastServices.
  ///
  /// In fr, this message translates to:
  /// **'Dernières prestations'**
  String get lastServices;

  /// No description provided for @tabDone.
  ///
  /// In fr, this message translates to:
  /// **'Terminées'**
  String get tabDone;

  /// No description provided for @tabOngoing.
  ///
  /// In fr, this message translates to:
  /// **'En cours'**
  String get tabOngoing;

  /// No description provided for @navHome.
  ///
  /// In fr, this message translates to:
  /// **'Accueil'**
  String get navHome;

  /// No description provided for @navMissions.
  ///
  /// In fr, this message translates to:
  /// **'Missions'**
  String get navMissions;

  /// No description provided for @navWallet.
  ///
  /// In fr, this message translates to:
  /// **'Portefeuille'**
  String get navWallet;

  /// No description provided for @navProfile.
  ///
  /// In fr, this message translates to:
  /// **'Profil'**
  String get navProfile;

  /// No description provided for @requestService.
  ///
  /// In fr, this message translates to:
  /// **'Demander un service'**
  String get requestService;

  /// No description provided for @firstRequestTitle.
  ///
  /// In fr, this message translates to:
  /// **'De quoi avez-vous besoin ?'**
  String get firstRequestTitle;

  /// No description provided for @whichService.
  ///
  /// In fr, this message translates to:
  /// **'Quel service ?'**
  String get whichService;

  /// No description provided for @notInList.
  ///
  /// In fr, this message translates to:
  /// **'Mon besoin n\'est pas dans la liste'**
  String get notInList;

  /// No description provided for @myMissions.
  ///
  /// In fr, this message translates to:
  /// **'Mes missions'**
  String get myMissions;

  /// No description provided for @noMissions.
  ///
  /// In fr, this message translates to:
  /// **'Rien ici pour l\'instant.'**
  String get noMissions;

  /// No description provided for @statusPending.
  ///
  /// In fr, this message translates to:
  /// **'En attente de devis'**
  String get statusPending;

  /// No description provided for @statusQuoted.
  ///
  /// In fr, this message translates to:
  /// **'{count} devis reçus'**
  String statusQuoted(int count);

  /// No description provided for @statusConfirmed.
  ///
  /// In fr, this message translates to:
  /// **'Prestataire choisi'**
  String get statusConfirmed;

  /// No description provided for @statusInProgress.
  ///
  /// In fr, this message translates to:
  /// **'{name} est en route'**
  String statusInProgress(String name);

  /// No description provided for @statusAwaiting.
  ///
  /// In fr, this message translates to:
  /// **'À confirmer'**
  String get statusAwaiting;

  /// No description provided for @statusCompleted.
  ///
  /// In fr, this message translates to:
  /// **'Terminée'**
  String get statusCompleted;

  /// No description provided for @statusCancelled.
  ///
  /// In fr, this message translates to:
  /// **'Annulée'**
  String get statusCancelled;

  /// No description provided for @statusDisputed.
  ///
  /// In fr, this message translates to:
  /// **'Litige en cours'**
  String get statusDisputed;

  /// No description provided for @compareQuotes.
  ///
  /// In fr, this message translates to:
  /// **'Comparer les devis'**
  String get compareQuotes;

  /// No description provided for @viewQuotes.
  ///
  /// In fr, this message translates to:
  /// **'Voir les devis'**
  String get viewQuotes;

  /// No description provided for @follow.
  ///
  /// In fr, this message translates to:
  /// **'Suivre'**
  String get follow;

  /// No description provided for @paySecured.
  ///
  /// In fr, this message translates to:
  /// **'Sécurisé par Nexis Hub'**
  String get paySecured;

  /// No description provided for @payReleased.
  ///
  /// In fr, this message translates to:
  /// **'Versé au prestataire'**
  String get payReleased;

  /// No description provided for @payRefunded.
  ///
  /// In fr, this message translates to:
  /// **'Remboursé'**
  String get payRefunded;

  /// No description provided for @payBlocked.
  ///
  /// In fr, this message translates to:
  /// **'Bloqué (litige)'**
  String get payBlocked;

  /// No description provided for @payAvailable.
  ///
  /// In fr, this message translates to:
  /// **'Disponible'**
  String get payAvailable;

  /// No description provided for @movements.
  ///
  /// In fr, this message translates to:
  /// **'Mouvements'**
  String get movements;

  /// No description provided for @seeAll.
  ///
  /// In fr, this message translates to:
  /// **'Tout voir'**
  String get seeAll;

  /// No description provided for @today.
  ///
  /// In fr, this message translates to:
  /// **'Aujourd\'hui'**
  String get today;

  /// No description provided for @yesterday.
  ///
  /// In fr, this message translates to:
  /// **'Hier'**
  String get yesterday;

  /// No description provided for @comingSoon.
  ///
  /// In fr, this message translates to:
  /// **'Bientôt dans l\'app'**
  String get comingSoon;

  /// No description provided for @comingSoonText.
  ///
  /// In fr, this message translates to:
  /// **'Cet écran arrive dans une prochaine version.'**
  String get comingSoonText;

  /// No description provided for @ok.
  ///
  /// In fr, this message translates to:
  /// **'Compris'**
  String get ok;

  /// No description provided for @phone.
  ///
  /// In fr, this message translates to:
  /// **'Téléphone'**
  String get phone;

  /// No description provided for @commune.
  ///
  /// In fr, this message translates to:
  /// **'Commune'**
  String get commune;

  /// No description provided for @language.
  ///
  /// In fr, this message translates to:
  /// **'Langue'**
  String get language;

  /// No description provided for @myDevices.
  ///
  /// In fr, this message translates to:
  /// **'Mes appareils'**
  String get myDevices;

  /// No description provided for @help.
  ///
  /// In fr, this message translates to:
  /// **'Aide'**
  String get help;

  /// No description provided for @becomeProvider.
  ///
  /// In fr, this message translates to:
  /// **'Devenir prestataire'**
  String get becomeProvider;

  /// No description provided for @becomeProviderSub.
  ///
  /// In fr, this message translates to:
  /// **'Le même compte, le même portefeuille'**
  String get becomeProviderSub;

  /// No description provided for @signOut.
  ///
  /// In fr, this message translates to:
  /// **'Se déconnecter'**
  String get signOut;

  /// No description provided for @clientBadge.
  ///
  /// In fr, this message translates to:
  /// **'Client'**
  String get clientBadge;

  /// No description provided for @back.
  ///
  /// In fr, this message translates to:
  /// **'Retour'**
  String get back;

  /// No description provided for @editProfile.
  ///
  /// In fr, this message translates to:
  /// **'Modifier'**
  String get editProfile;

  /// No description provided for @pickServiceHint.
  ///
  /// In fr, this message translates to:
  /// **'Choisissez, nous nous occupons du reste.'**
  String get pickServiceHint;

  /// No description provided for @otherNeed.
  ///
  /// In fr, this message translates to:
  /// **'Autre'**
  String get otherNeed;

  /// No description provided for @close.
  ///
  /// In fr, this message translates to:
  /// **'Fermer'**
  String get close;

  /// No description provided for @quotesPill.
  ///
  /// In fr, this message translates to:
  /// **'{count} devis'**
  String quotesPill(int count);

  /// No description provided for @waitingPill.
  ///
  /// In fr, this message translates to:
  /// **'En attente'**
  String get waitingPill;

  /// No description provided for @legalTerms.
  ///
  /// In fr, this message translates to:
  /// **'Conditions d\'utilisation'**
  String get legalTerms;

  /// No description provided for @legalPrivacy.
  ///
  /// In fr, this message translates to:
  /// **'Politique de confidentialité'**
  String get legalPrivacy;

  /// No description provided for @notReceived.
  ///
  /// In fr, this message translates to:
  /// **'Pas reçu ?'**
  String get notReceived;

  /// No description provided for @resendIn.
  ///
  /// In fr, this message translates to:
  /// **'Renvoyer dans {time}'**
  String resendIn(String time);

  /// No description provided for @resendNow.
  ///
  /// In fr, this message translates to:
  /// **'Renvoyer le code'**
  String get resendNow;

  /// No description provided for @myInfo.
  ///
  /// In fr, this message translates to:
  /// **'Mes informations'**
  String get myInfo;

  /// No description provided for @myInfoSub.
  ///
  /// In fr, this message translates to:
  /// **'Nom, photo, commune'**
  String get myInfoSub;

  /// No description provided for @devicesCount.
  ///
  /// In fr, this message translates to:
  /// **'{count, plural, =1{1 appareil connecté} other{{count} appareils connectés}}'**
  String devicesCount(int count);

  /// No description provided for @helpDisputes.
  ///
  /// In fr, this message translates to:
  /// **'Aide et litiges'**
  String get helpDisputes;

  /// No description provided for @helpDisputesSub.
  ///
  /// In fr, this message translates to:
  /// **'Un souci sur une mission'**
  String get helpDisputesSub;

  /// No description provided for @spaceClient.
  ///
  /// In fr, this message translates to:
  /// **'Client'**
  String get spaceClient;

  /// No description provided for @spaceProvider.
  ///
  /// In fr, this message translates to:
  /// **'Prestataire'**
  String get spaceProvider;

  /// No description provided for @bestRated.
  ///
  /// In fr, this message translates to:
  /// **'Le mieux noté'**
  String get bestRated;

  /// No description provided for @chooseProvider.
  ///
  /// In fr, this message translates to:
  /// **'Choisir {name}'**
  String chooseProvider(String name);

  /// No description provided for @securedUntilDone.
  ///
  /// In fr, this message translates to:
  /// **'Votre argent reste sécurisé par Nexis Hub jusqu\'à ce que vous confirmiez que c\'est fait.'**
  String get securedUntilDone;

  /// No description provided for @payTitle.
  ///
  /// In fr, this message translates to:
  /// **'Payer'**
  String get payTitle;

  /// No description provided for @payWith.
  ///
  /// In fr, this message translates to:
  /// **'Payer avec'**
  String get payWith;

  /// No description provided for @addNumber.
  ///
  /// In fr, this message translates to:
  /// **'Ajouter un numéro'**
  String get addNumber;

  /// No description provided for @paySecuredNote.
  ///
  /// In fr, this message translates to:
  /// **'Sécurisé par Nexis Hub : {name} reçoit l\'argent quand vous confirmez que c\'est fait.'**
  String paySecuredNote(String name);

  /// No description provided for @payAmount.
  ///
  /// In fr, this message translates to:
  /// **'Payer {amount}'**
  String payAmount(String amount);

  /// No description provided for @pendingTitle.
  ///
  /// In fr, this message translates to:
  /// **'Validez sur votre téléphone'**
  String get pendingTitle;

  /// No description provided for @pendingText.
  ///
  /// In fr, this message translates to:
  /// **'{operator} vous envoie une demande de {amount}. Tapez votre code secret Mobile Money pour l\'accepter.'**
  String pendingText(String operator, String amount);

  /// No description provided for @pendingSent.
  ///
  /// In fr, this message translates to:
  /// **'Demande envoyée à {operator}'**
  String pendingSent(String operator);

  /// No description provided for @pendingWaiting.
  ///
  /// In fr, this message translates to:
  /// **'En attente de confirmation'**
  String get pendingWaiting;

  /// No description provided for @pendingWithin.
  ///
  /// In fr, this message translates to:
  /// **'Vous avez 5 minutes'**
  String get pendingWithin;

  /// No description provided for @pendingSecured.
  ///
  /// In fr, this message translates to:
  /// **'Argent sécurisé par Nexis Hub'**
  String get pendingSecured;

  /// No description provided for @pendingNotify.
  ///
  /// In fr, this message translates to:
  /// **'Nous prévenons {name} tout de suite'**
  String pendingNotify(String name);

  /// No description provided for @nothingReceived.
  ///
  /// In fr, this message translates to:
  /// **'Je n\'ai rien reçu'**
  String get nothingReceived;

  /// No description provided for @paymentTitle.
  ///
  /// In fr, this message translates to:
  /// **'Paiement'**
  String get paymentTitle;

  /// No description provided for @trackTitle.
  ///
  /// In fr, this message translates to:
  /// **'Suivi'**
  String get trackTitle;

  /// No description provided for @distanceAway.
  ///
  /// In fr, this message translates to:
  /// **'{name} est à {km} km'**
  String distanceAway(String name, String km);

  /// No description provided for @trackingOff.
  ///
  /// In fr, this message translates to:
  /// **'Suivi non activé'**
  String get trackingOff;

  /// No description provided for @stepPaid.
  ///
  /// In fr, this message translates to:
  /// **'Payé'**
  String get stepPaid;

  /// No description provided for @stepOnTheWay.
  ///
  /// In fr, this message translates to:
  /// **'En route'**
  String get stepOnTheWay;

  /// No description provided for @stepOnTheWaySub.
  ///
  /// In fr, this message translates to:
  /// **'Suivi de position activé'**
  String get stepOnTheWaySub;

  /// No description provided for @stepOnSite.
  ///
  /// In fr, this message translates to:
  /// **'Sur place'**
  String get stepOnSite;

  /// No description provided for @stepWorkDone.
  ///
  /// In fr, this message translates to:
  /// **'Travail terminé'**
  String get stepWorkDone;

  /// No description provided for @stepConfirm.
  ///
  /// In fr, this message translates to:
  /// **'Vous confirmez, {name} reçoit l\'argent'**
  String stepConfirm(String name);

  /// No description provided for @confirmAction.
  ///
  /// In fr, this message translates to:
  /// **'Confirmer'**
  String get confirmAction;

  /// No description provided for @confirmQuestion.
  ///
  /// In fr, this message translates to:
  /// **'{name} a terminé.\nC\'est bien fait ?'**
  String confirmQuestion(String name);

  /// No description provided for @confirmText.
  ///
  /// In fr, this message translates to:
  /// **'Quand vous confirmez, Nexis Hub verse l\'argent sécurisé à {name}.'**
  String confirmText(String name);

  /// No description provided for @paidTo.
  ///
  /// In fr, this message translates to:
  /// **'Versé à {name}'**
  String paidTo(String name);

  /// No description provided for @amountFixed.
  ///
  /// In fr, this message translates to:
  /// **'Montant fixé par Nexis Hub au paiement'**
  String get amountFixed;

  /// No description provided for @report48h.
  ///
  /// In fr, this message translates to:
  /// **'Un souci ? Vous avez 48 h pour le signaler. L\'argent reste alors bloqué le temps que nous regardions avec vous deux.'**
  String get report48h;

  /// No description provided for @yesDone.
  ///
  /// In fr, this message translates to:
  /// **'Oui, c\'est fait'**
  String get yesDone;

  /// No description provided for @reportProblem.
  ///
  /// In fr, this message translates to:
  /// **'Signaler un problème'**
  String get reportProblem;

  /// No description provided for @confirmedToast.
  ///
  /// In fr, this message translates to:
  /// **'Merci ! {name} reçoit l\'argent.'**
  String confirmedToast(String name);

  /// No description provided for @callLabel.
  ///
  /// In fr, this message translates to:
  /// **'Appeler'**
  String get callLabel;

  /// No description provided for @messageLabel.
  ///
  /// In fr, this message translates to:
  /// **'Écrire'**
  String get messageLabel;

  /// No description provided for @whatHappened.
  ///
  /// In fr, this message translates to:
  /// **'Que s\'est-il passé ?'**
  String get whatHappened;

  /// No description provided for @reasonNotFinished.
  ///
  /// In fr, this message translates to:
  /// **'Le travail n\'est pas fini'**
  String get reasonNotFinished;

  /// No description provided for @reasonBadWork.
  ///
  /// In fr, this message translates to:
  /// **'Le travail est mal fait'**
  String get reasonBadWork;

  /// No description provided for @reasonNoShow.
  ///
  /// In fr, this message translates to:
  /// **'Le prestataire n\'est pas venu'**
  String get reasonNoShow;

  /// No description provided for @reasonOther.
  ///
  /// In fr, this message translates to:
  /// **'Autre problème'**
  String get reasonOther;

  /// No description provided for @reportHint.
  ///
  /// In fr, this message translates to:
  /// **'Racontez en quelques mots ce qui ne va pas.'**
  String get reportHint;

  /// No description provided for @addPhoto.
  ///
  /// In fr, this message translates to:
  /// **'Ajouter une photo'**
  String get addPhoto;

  /// No description provided for @reportFrozen.
  ///
  /// In fr, this message translates to:
  /// **'Les {amount} sont bloqués le temps que nous regardions avec vous deux. Personne ne peut y toucher.'**
  String reportFrozen(String amount);

  /// No description provided for @sendReport.
  ///
  /// In fr, this message translates to:
  /// **'Envoyer le signalement'**
  String get sendReport;

  /// No description provided for @reportFailed.
  ///
  /// In fr, this message translates to:
  /// **'Le signalement n\'est pas parti. Réessayez dans un instant.'**
  String get reportFailed;

  /// No description provided for @disputeTitle.
  ///
  /// In fr, this message translates to:
  /// **'Litige'**
  String get disputeTitle;

  /// No description provided for @nobodyTouches.
  ///
  /// In fr, this message translates to:
  /// **'Personne ne peut y toucher'**
  String get nobodyTouches;

  /// No description provided for @youReported.
  ///
  /// In fr, this message translates to:
  /// **'Vous avez signalé'**
  String get youReported;

  /// No description provided for @photosCount.
  ///
  /// In fr, this message translates to:
  /// **'{count, plural, =0{sans photo} =1{1 photo} other{{count} photos}}'**
  String photosCount(int count);

  /// No description provided for @providerReplied.
  ///
  /// In fr, this message translates to:
  /// **'{name} a répondu'**
  String providerReplied(String name);

  /// No description provided for @nexisLooking.
  ///
  /// In fr, this message translates to:
  /// **'Nexis Hub regarde'**
  String get nexisLooking;

  /// No description provided for @nexisLookingSub.
  ///
  /// In fr, this message translates to:
  /// **'Réponse sous 48 h · nous pouvons vous appeler'**
  String get nexisLookingSub;

  /// No description provided for @decisionStep.
  ///
  /// In fr, this message translates to:
  /// **'Décision et argent'**
  String get decisionStep;

  /// No description provided for @decisionStepSub.
  ///
  /// In fr, this message translates to:
  /// **'Versé, remboursé ou partagé'**
  String get decisionStepSub;

  /// No description provided for @settleHint.
  ///
  /// In fr, this message translates to:
  /// **'Vous pouvez encore vous arranger avec {name}. Si vous êtes d\'accord, dites-le ici et nous clôturons le litige.'**
  String settleHint(String name);

  /// No description provided for @writeNexis.
  ///
  /// In fr, this message translates to:
  /// **'Écrire à Nexis Hub'**
  String get writeNexis;

  /// No description provided for @weSettled.
  ///
  /// In fr, this message translates to:
  /// **'Nous nous sommes arrangés'**
  String get weSettled;

  /// No description provided for @disputeOver.
  ///
  /// In fr, this message translates to:
  /// **'Litige terminé'**
  String get disputeOver;

  /// No description provided for @outcomeRefundTitle.
  ///
  /// In fr, this message translates to:
  /// **'Nous vous remboursons'**
  String get outcomeRefundTitle;

  /// No description provided for @outcomeRefundText.
  ///
  /// In fr, this message translates to:
  /// **'Après avoir regardé le dossier et parlé avec {name}, Nexis Hub a décidé de vous rembourser. L\'argent arrive dans votre portefeuille dans 3 jours si personne ne conteste.'**
  String outcomeRefundText(String name);

  /// No description provided for @outcomeReleaseTitle.
  ///
  /// In fr, this message translates to:
  /// **'L\'argent va à {name}'**
  String outcomeReleaseTitle(String name);

  /// No description provided for @outcomeReleaseText.
  ///
  /// In fr, this message translates to:
  /// **'Après avoir regardé le dossier avec vous deux, Nexis Hub a décidé que l\'argent revient à {name}. Il part dans 3 jours si personne ne conteste.'**
  String outcomeReleaseText(String name);

  /// No description provided for @outcomeSplitTitle.
  ///
  /// In fr, this message translates to:
  /// **'L\'argent est partagé'**
  String get outcomeSplitTitle;

  /// No description provided for @outcomeSplitText.
  ///
  /// In fr, this message translates to:
  /// **'Après avoir regardé le dossier avec vous deux, Nexis Hub a décidé de partager l\'argent entre vous et {name}. Votre part arrive dans votre portefeuille dans 3 jours si personne ne conteste.'**
  String outcomeSplitText(String name);

  /// No description provided for @toRefundYou.
  ///
  /// In fr, this message translates to:
  /// **'À vous rembourser'**
  String get toRefundYou;

  /// No description provided for @forProvider.
  ///
  /// In fr, this message translates to:
  /// **'Pour {name}'**
  String forProvider(String name);

  /// No description provided for @blockedDaysLeft.
  ///
  /// In fr, this message translates to:
  /// **'{count, plural, =1{Bloqué (litige) · encore 1 jour} other{Bloqué (litige) · encore {count} jours}}'**
  String blockedDaysLeft(int count);

  /// No description provided for @contestHint.
  ///
  /// In fr, this message translates to:
  /// **'{count, plural, =1{Pas d\'accord ? Vous avez encore 1 jour pour demander à revoir la décision. L\'argent reste bloqué pendant ce temps.} other{Pas d\'accord ? Vous avez {count} jours pour demander à revoir la décision. L\'argent reste bloqué pendant ce temps.}}'**
  String contestHint(int count);

  /// No description provided for @seeWallet.
  ///
  /// In fr, this message translates to:
  /// **'Voir mon portefeuille'**
  String get seeWallet;

  /// No description provided for @inService.
  ///
  /// In fr, this message translates to:
  /// **'En service'**
  String get inService;

  /// No description provided for @offService.
  ///
  /// In fr, this message translates to:
  /// **'Hors service'**
  String get offService;

  /// No description provided for @inServiceSub.
  ///
  /// In fr, this message translates to:
  /// **'Vous recevez les demandes de {communes}'**
  String inServiceSub(String communes);

  /// No description provided for @offServiceSub.
  ///
  /// In fr, this message translates to:
  /// **'Vous ne recevez pas de nouvelles demandes'**
  String get offServiceSub;

  /// No description provided for @offServiceHint.
  ///
  /// In fr, this message translates to:
  /// **'Active « En service » pour recevoir les demandes des clients.'**
  String get offServiceHint;

  /// No description provided for @andList.
  ///
  /// In fr, this message translates to:
  /// **'{head} et {last}'**
  String andList(String head, String last);

  /// No description provided for @securedUntilConfirm.
  ///
  /// In fr, this message translates to:
  /// **'{amount} sécurisés, versés quand le client confirme'**
  String securedUntilConfirm(String amount);

  /// No description provided for @newRequests.
  ///
  /// In fr, this message translates to:
  /// **'Nouvelles demandes'**
  String get newRequests;

  /// No description provided for @noRequests.
  ///
  /// In fr, this message translates to:
  /// **'Pas de nouvelle demande pour l\'instant.'**
  String get noRequests;

  /// No description provided for @jobsInProgress.
  ///
  /// In fr, this message translates to:
  /// **'Missions en cours'**
  String get jobsInProgress;

  /// No description provided for @newPill.
  ///
  /// In fr, this message translates to:
  /// **'Nouveau'**
  String get newPill;

  /// No description provided for @minutesAgo.
  ///
  /// In fr, this message translates to:
  /// **'{count} min'**
  String minutesAgo(int count);

  /// No description provided for @hoursAgo.
  ///
  /// In fr, this message translates to:
  /// **'{count} h'**
  String hoursAgo(int count);

  /// No description provided for @quoteSentPill.
  ///
  /// In fr, this message translates to:
  /// **'Devis envoyé'**
  String get quoteSentPill;

  /// No description provided for @sendAQuote.
  ///
  /// In fr, this message translates to:
  /// **'Envoyer un devis'**
  String get sendAQuote;

  /// No description provided for @sendTheQuote.
  ///
  /// In fr, this message translates to:
  /// **'Envoyer le devis'**
  String get sendTheQuote;

  /// No description provided for @yourPrice.
  ///
  /// In fr, this message translates to:
  /// **'Votre prix'**
  String get yourPrice;

  /// No description provided for @priceAsked.
  ///
  /// In fr, this message translates to:
  /// **'Montant demandé au client'**
  String get priceAsked;

  /// No description provided for @changeCurrency.
  ///
  /// In fr, this message translates to:
  /// **'Changer de devise'**
  String get changeCurrency;

  /// No description provided for @yourSlot.
  ///
  /// In fr, this message translates to:
  /// **'Votre créneau'**
  String get yourSlot;

  /// No description provided for @otherSlot.
  ///
  /// In fr, this message translates to:
  /// **'Autre'**
  String get otherSlot;

  /// No description provided for @quoteSentToast.
  ///
  /// In fr, this message translates to:
  /// **'Devis envoyé. Vous serez prévenu si le client le choisit.'**
  String get quoteSentToast;

  /// No description provided for @quoteFailed.
  ///
  /// In fr, this message translates to:
  /// **'Le devis n\'est pas parti. Réessayez dans un instant.'**
  String get quoteFailed;

  /// No description provided for @actionFailed.
  ///
  /// In fr, this message translates to:
  /// **'Cela n\'a pas fonctionné. Réessayez dans un instant.'**
  String get actionFailed;

  /// No description provided for @jobTitle.
  ///
  /// In fr, this message translates to:
  /// **'Mission'**
  String get jobTitle;

  /// No description provided for @jobToStart.
  ///
  /// In fr, this message translates to:
  /// **'Payé, à vous de partir'**
  String get jobToStart;

  /// No description provided for @jobOnTheWay.
  ///
  /// In fr, this message translates to:
  /// **'En route'**
  String get jobOnTheWay;

  /// No description provided for @jobArrivalPending.
  ///
  /// In fr, this message translates to:
  /// **'Arrivée à confirmer par {name}'**
  String jobArrivalPending(String name);

  /// No description provided for @jobOnSite.
  ///
  /// In fr, this message translates to:
  /// **'Sur place'**
  String get jobOnSite;

  /// No description provided for @jobWaitingClient.
  ///
  /// In fr, this message translates to:
  /// **'Terminé, {name} doit confirmer'**
  String jobWaitingClient(String name);

  /// No description provided for @shareLocation.
  ///
  /// In fr, this message translates to:
  /// **'Partager ma position'**
  String get shareLocation;

  /// No description provided for @shareLocationSub.
  ///
  /// In fr, this message translates to:
  /// **'{name} voit la distance jusqu\'à votre arrivée'**
  String shareLocationSub(String name);

  /// No description provided for @pStepPaid.
  ///
  /// In fr, this message translates to:
  /// **'Client a payé'**
  String get pStepPaid;

  /// No description provided for @pStepLeft.
  ///
  /// In fr, this message translates to:
  /// **'Je suis parti'**
  String get pStepLeft;

  /// No description provided for @pStepArrive.
  ///
  /// In fr, this message translates to:
  /// **'J\'arrive sur place'**
  String get pStepArrive;

  /// No description provided for @pStepOnSite.
  ///
  /// In fr, this message translates to:
  /// **'Je suis sur place'**
  String get pStepOnSite;

  /// No description provided for @pStepDone.
  ///
  /// In fr, this message translates to:
  /// **'J\'ai terminé'**
  String get pStepDone;

  /// No description provided for @btnLeave.
  ///
  /// In fr, this message translates to:
  /// **'Je pars'**
  String get btnLeave;

  /// No description provided for @btnArrived.
  ///
  /// In fr, this message translates to:
  /// **'Je suis arrivé'**
  String get btnArrived;

  /// No description provided for @btnFinished.
  ///
  /// In fr, this message translates to:
  /// **'J\'ai terminé'**
  String get btnFinished;

  /// No description provided for @callClient.
  ///
  /// In fr, this message translates to:
  /// **'Appeler {name}'**
  String callClient(String name);

  /// No description provided for @arrivalWaiting.
  ///
  /// In fr, this message translates to:
  /// **'{name} doit confirmer votre arrivée sur son téléphone. Vous pouvez aussi taper son code de présence.'**
  String arrivalWaiting(String name);

  /// No description provided for @arrivalWaitingSub.
  ///
  /// In fr, this message translates to:
  /// **'En attente de {name}'**
  String arrivalWaitingSub(String name);

  /// No description provided for @arrivalConfirmed.
  ///
  /// In fr, this message translates to:
  /// **'Arrivée confirmée'**
  String get arrivalConfirmed;

  /// No description provided for @presenceCode.
  ///
  /// In fr, this message translates to:
  /// **'Code de présence du client'**
  String get presenceCode;

  /// No description provided for @confirmCode.
  ///
  /// In fr, this message translates to:
  /// **'Valider'**
  String get confirmCode;

  /// No description provided for @wrongCode.
  ///
  /// In fr, this message translates to:
  /// **'{count, plural, =1{Code incorrect. Encore 1 essai.} other{Code incorrect. Encore {count} essais.}}'**
  String wrongCode(int count);

  /// No description provided for @codeLocked.
  ///
  /// In fr, this message translates to:
  /// **'Trop d\'essais. Seul {name} peut maintenant confirmer votre arrivée.'**
  String codeLocked(String name);

  /// No description provided for @finishedNote.
  ///
  /// In fr, this message translates to:
  /// **'{name} a 48 h pour confirmer ou signaler un problème. Sans réponse, l\'argent vous est versé au bout de 48 h.'**
  String finishedNote(String name);

  /// No description provided for @smsSub.
  ///
  /// In fr, this message translates to:
  /// **'Un message texte sur ce numéro'**
  String get smsSub;

  /// No description provided for @codeSentBySms.
  ///
  /// In fr, this message translates to:
  /// **'Envoyé par SMS au {phone}.'**
  String codeSentBySms(String phone);

  /// No description provided for @noCodeChannel.
  ///
  /// In fr, this message translates to:
  /// **'Aucun canal n\'est disponible pour le moment. Réessayez dans un instant.'**
  String get noCodeChannel;

  /// No description provided for @numberNotCongolese.
  ///
  /// In fr, this message translates to:
  /// **'Ce numéro ne semble pas être un numéro congolais.'**
  String get numberNotCongolese;

  /// No description provided for @neverAskCode.
  ///
  /// In fr, this message translates to:
  /// **'Nous ne vous demanderons jamais ce code par téléphone ni par message.'**
  String get neverAskCode;

  /// No description provided for @enterCode.
  ///
  /// In fr, this message translates to:
  /// **'Entrez le code'**
  String get enterCode;

  /// No description provided for @codeHint.
  ///
  /// In fr, this message translates to:
  /// **'Valable 10 minutes. Ne le partagez avec personne.'**
  String get codeHint;

  /// No description provided for @codeSentToast.
  ///
  /// In fr, this message translates to:
  /// **'Code envoyé par {channel}.'**
  String codeSentToast(String channel);

  /// No description provided for @codeResentToast.
  ///
  /// In fr, this message translates to:
  /// **'Nouveau code envoyé par {channel}.'**
  String codeResentToast(String channel);

  /// No description provided for @receiveInstead.
  ///
  /// In fr, this message translates to:
  /// **'Recevoir plutôt par {channel}'**
  String receiveInstead(String channel);

  /// No description provided for @eveningHome.
  ///
  /// In fr, this message translates to:
  /// **'Bonsoir, {name}'**
  String eveningHome(String name);

  /// No description provided for @helloHome.
  ///
  /// In fr, this message translates to:
  /// **'Bonjour, {name}'**
  String helloHome(String name);

  /// No description provided for @heldForMissions.
  ///
  /// In fr, this message translates to:
  /// **'{amount} bloqués pour vos missions en cours'**
  String heldForMissions(String amount);

  /// No description provided for @heldWhy.
  ///
  /// In fr, this message translates to:
  /// **'Pourquoi ces fonds sont bloqués'**
  String get heldWhy;

  /// No description provided for @heldTip.
  ///
  /// In fr, this message translates to:
  /// **'Cet argent reste à vous. Il est mis de côté pour payer le professionnel quand la mission est terminée et que vous l\'avez confirmée.'**
  String get heldTip;

  /// No description provided for @currency.
  ///
  /// In fr, this message translates to:
  /// **'Devise'**
  String get currency;

  /// No description provided for @quickActions.
  ///
  /// In fr, this message translates to:
  /// **'Actions rapides'**
  String get quickActions;

  /// No description provided for @reviewsCount.
  ///
  /// In fr, this message translates to:
  /// **'{count} avis'**
  String reviewsCount(int count);

  /// No description provided for @completedOn.
  ///
  /// In fr, this message translates to:
  /// **'Terminée le {date}'**
  String completedOn(String date);

  /// No description provided for @followMission.
  ///
  /// In fr, this message translates to:
  /// **'Suivre la mission'**
  String get followMission;

  /// No description provided for @seeMissions.
  ///
  /// In fr, this message translates to:
  /// **'Voir les {count} missions'**
  String seeMissions(int count);

  /// No description provided for @recentMovements.
  ///
  /// In fr, this message translates to:
  /// **'Derniers mouvements'**
  String get recentMovements;

  /// No description provided for @newBadge.
  ///
  /// In fr, this message translates to:
  /// **'Nouveau'**
  String get newBadge;

  /// No description provided for @allServices.
  ///
  /// In fr, this message translates to:
  /// **'Tous les services'**
  String get allServices;

  /// No description provided for @searchService.
  ///
  /// In fr, this message translates to:
  /// **'Rechercher un service'**
  String get searchService;

  /// No description provided for @recents.
  ///
  /// In fr, this message translates to:
  /// **'Récents'**
  String get recents;

  /// No description provided for @newAndRecommended.
  ///
  /// In fr, this message translates to:
  /// **'Nouveaux et recommandés'**
  String get newAndRecommended;

  /// No description provided for @requestedIn.
  ///
  /// In fr, this message translates to:
  /// **'Demandé en {month}'**
  String requestedIn(String month);

  /// No description provided for @requestedOn.
  ///
  /// In fr, this message translates to:
  /// **'Demandé le {date}'**
  String requestedOn(String date);

  /// No description provided for @addedThisWeek.
  ///
  /// In fr, this message translates to:
  /// **'Ajouté cette semaine'**
  String get addedThisWeek;

  /// No description provided for @recommendedForYou.
  ///
  /// In fr, this message translates to:
  /// **'Recommandé pour vous'**
  String get recommendedForYou;

  /// No description provided for @noServiceMatches.
  ///
  /// In fr, this message translates to:
  /// **'Aucun service ne correspond.'**
  String get noServiceMatches;

  /// No description provided for @cantFindService.
  ///
  /// In fr, this message translates to:
  /// **'Vous ne trouvez pas votre service ?'**
  String get cantFindService;

  /// No description provided for @cantFindHint.
  ///
  /// In fr, this message translates to:
  /// **'Décrivez votre besoin avec vos mots, nous le transmettons à l\'équipe.'**
  String get cantFindHint;

  /// No description provided for @describeNeed.
  ///
  /// In fr, this message translates to:
  /// **'Décrire mon besoin'**
  String get describeNeed;

  /// No description provided for @describeLead.
  ///
  /// In fr, this message translates to:
  /// **'Dites-nous ce dont vous avez besoin avec vos mots. L\'équipe Nexis Hub regarde votre demande et cherche le bon professionnel.'**
  String get describeLead;

  /// No description provided for @describeTypeLabel.
  ///
  /// In fr, this message translates to:
  /// **'Quel type de service ?'**
  String get describeTypeLabel;

  /// No description provided for @describeTypeHint.
  ///
  /// In fr, this message translates to:
  /// **'Par exemple : réparation de portail'**
  String get describeTypeHint;

  /// No description provided for @describeTextLabel.
  ///
  /// In fr, this message translates to:
  /// **'Décrivez votre besoin'**
  String get describeTextLabel;

  /// No description provided for @describeTextHint.
  ///
  /// In fr, this message translates to:
  /// **'Où, quoi, et pour quand si c\'est urgent'**
  String get describeTextHint;

  /// No description provided for @optional.
  ///
  /// In fr, this message translates to:
  /// **'facultatif'**
  String get optional;

  /// No description provided for @photos.
  ///
  /// In fr, this message translates to:
  /// **'Photos'**
  String get photos;

  /// No description provided for @addShort.
  ///
  /// In fr, this message translates to:
  /// **'Ajouter'**
  String get addShort;

  /// No description provided for @describeNoPay.
  ///
  /// In fr, this message translates to:
  /// **'Vous ne payez rien à cette étape. Vous êtes prévenu dans l\'app dès que nous avons une réponse.'**
  String get describeNoPay;

  /// No description provided for @sendRequest.
  ///
  /// In fr, this message translates to:
  /// **'Envoyer ma demande'**
  String get sendRequest;

  /// No description provided for @requestSent.
  ///
  /// In fr, this message translates to:
  /// **'Demande envoyée'**
  String get requestSent;

  /// No description provided for @requestSentText.
  ///
  /// In fr, this message translates to:
  /// **'Nous avons bien reçu votre demande. Vous serez prévenu dans l\'app, et sur WhatsApp ou Telegram, dès que nous avons une réponse.'**
  String get requestSentText;

  /// No description provided for @backHome.
  ///
  /// In fr, this message translates to:
  /// **'Retour à l\'accueil'**
  String get backHome;

  /// No description provided for @requestNotSent.
  ///
  /// In fr, this message translates to:
  /// **'La demande n\'est pas partie. Réessayez dans un instant.'**
  String get requestNotSent;

  /// No description provided for @notifications.
  ///
  /// In fr, this message translates to:
  /// **'Notifications'**
  String get notifications;

  /// No description provided for @notificationsSub.
  ///
  /// In fr, this message translates to:
  /// **'WhatsApp et dans l\'app'**
  String get notificationsSub;

  /// No description provided for @termsVersion.
  ///
  /// In fr, this message translates to:
  /// **'Version du {date}'**
  String termsVersion(String date);

  /// No description provided for @securedByNexis.
  ///
  /// In fr, this message translates to:
  /// **'Sécurisé par Nexis Hub'**
  String get securedByNexis;

  /// No description provided for @signupTitle.
  ///
  /// In fr, this message translates to:
  /// **'Faisons connaissance'**
  String get signupTitle;

  /// No description provided for @signupFirstName.
  ///
  /// In fr, this message translates to:
  /// **'Prénom'**
  String get signupFirstName;

  /// No description provided for @signupLastName.
  ///
  /// In fr, this message translates to:
  /// **'Nom'**
  String get signupLastName;

  /// No description provided for @signupOtherCommune.
  ///
  /// In fr, this message translates to:
  /// **'Autre commune'**
  String get signupOtherCommune;

  /// No description provided for @signupDemoNotice.
  ///
  /// In fr, this message translates to:
  /// **'Inscription de démonstration. Utilisez des informations fictives.'**
  String get signupDemoNotice;

  /// No description provided for @signupReadTerms.
  ///
  /// In fr, this message translates to:
  /// **'Lire les CGU'**
  String get signupReadTerms;

  /// No description provided for @signupAcceptTerms.
  ///
  /// In fr, this message translates to:
  /// **'J’ai lu et j’accepte les CGU'**
  String get signupAcceptTerms;

  /// No description provided for @signupCreateProfile.
  ///
  /// In fr, this message translates to:
  /// **'Créer mon profil'**
  String get signupCreateProfile;

  /// No description provided for @signupFailed.
  ///
  /// In fr, this message translates to:
  /// **'Le profil n’a pas pu être créé. Vérifiez les informations et réessayez.'**
  String get signupFailed;

  /// No description provided for @signupDemoTerms.
  ///
  /// In fr, this message translates to:
  /// **'Document de démonstration. Cet écran sert à tester la lecture et l’acceptation des conditions. Les profils créés, les missions et les paiements de cet aperçu sont fictifs. Les informations de cette inscription sont effacées au rechargement de l’app.'**
  String get signupDemoTerms;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en', 'fr', 'ln'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return AppLocalizationsEn();
    case 'fr':
      return AppLocalizationsFr();
    case 'ln':
      return AppLocalizationsLn();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
