// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Lingala (`ln`).
class AppLocalizationsLn extends AppLocalizations {
  AppLocalizationsLn([String locale = 'ln']) : super(locale);

  @override
  String get previewBanner => 'Bomoni · makambo ya solo te';

  @override
  String get slogan => 'Epai bosembo ekutani na mosala.';

  @override
  String get welcomeIntro =>
      'Basali ya bosembo na Kinshasa. Mbongo na yo ebatelami tii okondima ete mosala esili malamu.';

  @override
  String get start => 'Kobanda';

  @override
  String get haveAccount => 'Nazali na compte';

  @override
  String get yourNumber => 'Nimero na yo';

  @override
  String get yourNumberIntro =>
      'Tokotindela yo code mpo na koyeba ete ezali yo.';

  @override
  String get receiveCodeBy => 'Kozwa code na';

  @override
  String get whatsappSub => 'Code ekoya na mwa ba seconde';

  @override
  String get telegramSub => 'Na bot ya Nexis Hub';

  @override
  String get receiveCode => 'Kozwa code';

  @override
  String get theCode => 'Code';

  @override
  String codeSentTo(String channel, String phone) {
    return 'Etindami na $channel na $phone';
  }

  @override
  String get demoCodeHint => 'Bomoni : kota ba chiffre 6 nyonso.';

  @override
  String get welcomeBack => 'Boyei malamu';

  @override
  String hello(String name) {
    return 'Mbote, $name';
  }

  @override
  String get myWallets => 'Esika na ngai ya mbongo';

  @override
  String get available => 'Ezali';

  @override
  String securedAmount(String amount) {
    return '$amount ebatelami';
  }

  @override
  String get hideAmounts => 'Kobomba mitango';

  @override
  String get showAmounts => 'Komonisa mitango';

  @override
  String get actionServices => 'Misala';

  @override
  String get actionDeposit => 'Kotia';

  @override
  String get actionWithdraw => 'Kobimisa';

  @override
  String get actionHistory => 'Makambo ya kala';

  @override
  String get actionMore => 'Mosusu';

  @override
  String get lastServices => 'Misala ya suka';

  @override
  String get tabDone => 'Esili';

  @override
  String get tabOngoing => 'Ezali kosalema';

  @override
  String get navHome => 'Ndako';

  @override
  String get navMissions => 'Misala';

  @override
  String get navWallet => 'Mbongo';

  @override
  String get navProfile => 'Profil';

  @override
  String get requestService => 'Kosenga mosala';

  @override
  String get whichService => 'Mosala nini ?';

  @override
  String get notInList => 'Mposa na ngai ezali na liste te';

  @override
  String get myMissions => 'Misala na ngai';

  @override
  String get noMissions => 'Eloko te mpo na sikoyo.';

  @override
  String get statusPending => 'Ezali kozela devis';

  @override
  String statusQuoted(int count) {
    return 'Devis $count eyei';
  }

  @override
  String get statusConfirmed => 'Mosali aponami';

  @override
  String statusInProgress(String name) {
    return '$name azali na nzela';
  }

  @override
  String get statusAwaiting => 'Ezali kozela ndingisa na yo';

  @override
  String get statusCompleted => 'Esili';

  @override
  String get statusCancelled => 'Ebongolami';

  @override
  String get statusDisputed => 'Likambo ezali kotalelama';

  @override
  String get compareQuotes => 'Kokokanisa ba devis';

  @override
  String get follow => 'Kolanda';

  @override
  String get paySecured => 'Ebatelami na Nexis Hub';

  @override
  String get payReleased => 'Epesami na mosali';

  @override
  String get payRefunded => 'Bazongisi';

  @override
  String get payBlocked => 'Ekangami (likambo)';

  @override
  String get payAvailable => 'Ezali';

  @override
  String get movements => 'Bokoti mpe bobimi';

  @override
  String get seeAll => 'Komona nyonso';

  @override
  String get today => 'Lelo';

  @override
  String get yesterday => 'Lobi';

  @override
  String get comingSoon => 'Ekoya noki';

  @override
  String get comingSoonText => 'Écran oyo ekoya na version ekolanda.';

  @override
  String get ok => 'Nayoki';

  @override
  String get phone => 'Telefone';

  @override
  String get commune => 'Commune';

  @override
  String get language => 'Lokota';

  @override
  String get myDevices => 'Ba appareil na ngai';

  @override
  String get help => 'Lisalisi';

  @override
  String get becomeProvider => 'Kokoma mosali';

  @override
  String get becomeProviderSub => 'Compte moko, esika ya mbongo moko';

  @override
  String get signOut => 'Kobima';

  @override
  String get clientBadge => 'Mosombi';

  @override
  String get back => 'Kozonga';

  @override
  String get editProfile => 'Kobongola';

  @override
  String get pickServiceHint => 'Pona, biso tokosala oyo etikali.';

  @override
  String get otherNeed => 'Mosusu';

  @override
  String get close => 'Kokanga';
}
