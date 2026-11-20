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
  /// **'Ton numéro'**
  String get yourNumber;

  /// No description provided for @yourNumberIntro.
  ///
  /// In fr, this message translates to:
  /// **'On t\'envoie un code pour vérifier que c\'est bien toi.'**
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

  /// No description provided for @theCode.
  ///
  /// In fr, this message translates to:
  /// **'Le code'**
  String get theCode;

  /// No description provided for @codeSentTo.
  ///
  /// In fr, this message translates to:
  /// **'Envoyé sur {channel} au {phone}'**
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
  
  /// Amount held until a client's confirmation.
  String walletLocked(String amount);

  /// Explains when the held funds are paid out.
  String get walletExplanation;

  /// Accessible label for the held-funds explanation.
  String get walletInfoLabel;

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
  /// **'Choisis, on s\'occupe du reste.'**
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

  /// No description provided for @legalText.
  ///
  /// In fr, this message translates to:
  /// **'En continuant, tu acceptes les {terms} et la {privacy}.'**
  String legalText(String terms, String privacy);

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

  /// No description provided for @receiveInstead.
  ///
  /// In fr, this message translates to:
  /// **'Recevoir plutôt par {channel}'**
  String receiveInstead(String channel);

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
  /// **'Ton argent reste sécurisé par Nexis Hub jusqu\'à ce que tu confirmes que c\'est fait.'**
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
  /// **'Sécurisé par Nexis Hub : {name} reçoit l\'argent quand tu confirmes que c\'est fait.'**
  String paySecuredNote(String name);

  /// No description provided for @payAmount.
  ///
  /// In fr, this message translates to:
  /// **'Payer {amount}'**
  String payAmount(String amount);

  /// No description provided for @pendingTitle.
  ///
  /// In fr, this message translates to:
  /// **'Valide sur ton téléphone'**
  String get pendingTitle;

  /// No description provided for @pendingText.
  ///
  /// In fr, this message translates to:
  /// **'{operator} t\'envoie une demande de {amount}. Tape ton code secret Mobile Money pour l\'accepter.'**
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
  /// **'Tu as 5 minutes'**
  String get pendingWithin;

  /// No description provided for @pendingSecured.
  ///
  /// In fr, this message translates to:
  /// **'Argent sécurisé par Nexis Hub'**
  String get pendingSecured;

  /// No description provided for @pendingNotify.
  ///
  /// In fr, this message translates to:
  /// **'On prévient {name} tout de suite'**
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
  /// **'Tu confirmes, {name} reçoit l\'argent'**
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
  /// **'Quand tu confirmes, Nexis Hub verse l\'argent sécurisé à {name}.'**
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
  /// **'Un souci ? Tu as 48 h pour le signaler. L\'argent reste alors bloqué le temps qu\'on regarde avec vous deux.'**
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
  /// **'Raconte en quelques mots ce qui ne va pas.'**
  String get reportHint;

  /// No description provided for @addPhoto.
  ///
  /// In fr, this message translates to:
  /// **'Ajouter une photo'**
  String get addPhoto;

  /// No description provided for @reportFrozen.
  ///
  /// In fr, this message translates to:
  /// **'Les {amount} sont bloqués le temps qu\'on regarde avec vous deux. Personne ne peut y toucher.'**
  String reportFrozen(String amount);

  /// No description provided for @sendReport.
  ///
  /// In fr, this message translates to:
  /// **'Envoyer le signalement'**
  String get sendReport;

  /// No description provided for @reportFailed.
  ///
  /// In fr, this message translates to:
  /// **'Le signalement n\'est pas parti. Réessaie dans un instant.'**
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
  /// **'Tu as signalé'**
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
  /// **'Réponse sous 48 h · on peut vous appeler'**
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
  /// **'Tu peux encore t\'arranger avec {name}. Si vous êtes d\'accord, dis-le ici et on clôt le litige.'**
  String settleHint(String name);

  /// No description provided for @writeNexis.
  ///
  /// In fr, this message translates to:
  /// **'Écrire à Nexis Hub'**
  String get writeNexis;

  /// No description provided for @weSettled.
  ///
  /// In fr, this message translates to:
  /// **'On s\'est arrangés'**
  String get weSettled;

  /// No description provided for @disputeOver.
  ///
  /// In fr, this message translates to:
  /// **'Litige terminé'**
  String get disputeOver;

  /// No description provided for @outcomeRefundTitle.
  ///
  /// In fr, this message translates to:
  /// **'On te rembourse'**
  String get outcomeRefundTitle;

  /// No description provided for @outcomeRefundText.
  ///
  /// In fr, this message translates to:
  /// **'Après avoir regardé le dossier et parlé avec {name}, Nexis Hub a décidé de te rembourser. L\'argent arrive dans ton portefeuille dans 3 jours si personne ne conteste.'**
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
  /// **'Après avoir regardé le dossier avec vous deux, Nexis Hub a décidé de partager l\'argent entre toi et {name}. Ta part arrive dans ton portefeuille dans 3 jours si personne ne conteste.'**
  String outcomeSplitText(String name);

  /// No description provided for @toRefundYou.
  ///
  /// In fr, this message translates to:
  /// **'À te rembourser'**
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
  /// **'{count, plural, =1{Pas d\'accord ? Tu as encore 1 jour pour demander à revoir la décision. L\'argent reste bloqué pendant ce temps.} other{Pas d\'accord ? Tu as {count} jours pour demander à revoir la décision. L\'argent reste bloqué pendant ce temps.}}'**
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
  /// **'Tu reçois les demandes de {communes}'**
  String inServiceSub(String communes);

  /// No description provided for @offServiceSub.
  ///
  /// In fr, this message translates to:
  /// **'Tu ne reçois pas de nouvelles demandes'**
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
  /// **'Ton prix'**
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
  /// **'Ton créneau'**
  String get yourSlot;

  /// No description provided for @otherSlot.
  ///
  /// In fr, this message translates to:
  /// **'Autre'**
  String get otherSlot;

  /// No description provided for @quoteSentToast.
  ///
  /// In fr, this message translates to:
  /// **'Devis envoyé. Tu seras prévenu si le client le choisit.'**
  String get quoteSentToast;

  /// No description provided for @quoteFailed.
  ///
  /// In fr, this message translates to:
  /// **'Le devis n\'est pas parti. Réessaie dans un instant.'**
  String get quoteFailed;

  /// No description provided for @actionFailed.
  ///
  /// In fr, this message translates to:
  /// **'Ça n\'a pas marché. Réessaie dans un instant.'**
  String get actionFailed;

  /// No description provided for @jobTitle.
  ///
  /// In fr, this message translates to:
  /// **'Mission'**
  String get jobTitle;

  /// No description provided for @jobToStart.
  ///
  /// In fr, this message translates to:
  /// **'Payé, à toi de partir'**
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
  /// **'{name} voit la distance jusqu\'à ton arrivée'**
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
  /// **'{name} doit confirmer ton arrivée sur son téléphone. Tu peux aussi taper son code de présence.'**
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
  /// **'Trop d\'essais. Seul {name} peut maintenant confirmer ton arrivée.'**
  String codeLocked(String name);

  /// No description provided for @finishedNote.
  ///
  /// In fr, this message translates to:
  /// **'{name} a 48 h pour confirmer ou signaler un problème. Sans réponse, l\'argent t\'est versé au bout de 48 h.'**
  String finishedNote(String name);
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
