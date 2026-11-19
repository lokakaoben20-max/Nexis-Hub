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

  /// No description provided for @previewBanner.
  ///
  /// In fr, this message translates to:
  /// **'Aperçu · données fictives'**
  String get previewBanner;

  /// No description provided for @slogan.
  ///
  /// In fr, this message translates to:
  /// **'Là où la confiance rencontre le service.'**
  String get slogan;

  /// No description provided for @welcomeIntro.
  ///
  /// In fr, this message translates to:
  /// **'Plomberie, électricité, nettoyage et plus encore à Kinshasa. Ton argent reste sécurisé jusqu\'à ce que tu confirmes.'**
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

  /// No description provided for @demoCodeHint.
  ///
  /// In fr, this message translates to:
  /// **'Aperçu : tape n\'importe quels 6 chiffres.'**
  String get demoCodeHint;

  /// No description provided for @welcomeBack.
  ///
  /// In fr, this message translates to:
  /// **'Bon retour'**
  String get welcomeBack;

  /// No description provided for @hello.
  ///
  /// In fr, this message translates to:
  /// **'Mbote, {name}'**
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
  /// **'Cet écran arrive dans une prochaine version de l\'aperçu.'**
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
