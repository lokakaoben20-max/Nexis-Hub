// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get previewBanner => 'Preview · sample data';

  @override
  String get slogan => 'Where trust meets service.';

  @override
  String get welcomeIntro =>
      'Plumbing, electrical, cleaning and more in Kinshasa. Your money stays secured until you confirm.';

  @override
  String get start => 'Get started';

  @override
  String get haveAccount => 'I already have an account';

  @override
  String get yourNumber => 'Your number';

  @override
  String get yourNumberIntro => 'We\'ll send you a code to check it\'s you.';

  @override
  String get receiveCodeBy => 'Get the code by';

  @override
  String get whatsappSub => 'The code arrives in seconds';

  @override
  String get telegramSub => 'With the Nexis Hub bot';

  @override
  String get receiveCode => 'Get the code';

  @override
  String get theCode => 'The code';

  @override
  String codeSentTo(String channel, String phone) {
    return 'Sent on $channel to $phone';
  }

  @override
  String get demoCodeHint => 'Preview: type any 6 digits.';

  @override
  String get welcomeBack => 'Welcome back';

  @override
  String hello(String name) {
    return 'Hello, $name';
  }

  @override
  String get myWallets => 'My wallets';

  @override
  String get available => 'Available';

  @override
  String securedAmount(String amount) {
    return '$amount secured';
  }

  @override
  String get hideAmounts => 'Hide amounts';

  @override
  String get showAmounts => 'Show amounts';

  @override
  String get actionServices => 'Services';

  @override
  String get actionDeposit => 'Deposit';

  @override
  String get actionWithdraw => 'Withdraw';

  @override
  String get actionHistory => 'History';

  @override
  String get actionMore => 'More';

  @override
  String get lastServices => 'Recent services';

  @override
  String get tabDone => 'Done';

  @override
  String get tabOngoing => 'Ongoing';

  @override
  String get navHome => 'Home';

  @override
  String get navMissions => 'Missions';

  @override
  String get navWallet => 'Wallet';

  @override
  String get navProfile => 'Profile';

  @override
  String get requestService => 'Request a service';

  @override
  String get whichService => 'Which service?';

  @override
  String get notInList => 'My need isn\'t in the list';

  @override
  String get myMissions => 'My missions';

  @override
  String get noMissions => 'Nothing here yet.';

  @override
  String get statusPending => 'Waiting for quotes';

  @override
  String statusQuoted(int count) {
    return '$count quotes received';
  }

  @override
  String get statusConfirmed => 'Provider chosen';

  @override
  String statusInProgress(String name) {
    return '$name is on the way';
  }

  @override
  String get statusAwaiting => 'To confirm';

  @override
  String get statusCompleted => 'Completed';

  @override
  String get statusCancelled => 'Cancelled';

  @override
  String get statusDisputed => 'Dispute open';

  @override
  String get compareQuotes => 'Compare quotes';

  @override
  String get follow => 'Track';

  @override
  String get paySecured => 'Secured by Nexis Hub';

  @override
  String get payReleased => 'Paid to provider';

  @override
  String get payRefunded => 'Refunded';

  @override
  String get payBlocked => 'On hold (dispute)';

  @override
  String get payAvailable => 'Available';

  @override
  String get movements => 'Activity';

  @override
  String get seeAll => 'See all';

  @override
  String get today => 'Today';

  @override
  String get yesterday => 'Yesterday';

  @override
  String get comingSoon => 'Coming soon';

  @override
  String get comingSoonText =>
      'This screen comes in a next version of the preview.';

  @override
  String get ok => 'Got it';

  @override
  String get phone => 'Phone';

  @override
  String get commune => 'Commune';

  @override
  String get language => 'Language';

  @override
  String get myDevices => 'My devices';

  @override
  String get help => 'Help';

  @override
  String get becomeProvider => 'Become a provider';

  @override
  String get becomeProviderSub => 'Same account, same wallet';

  @override
  String get signOut => 'Sign out';

  @override
  String get clientBadge => 'Client';

  @override
  String get back => 'Back';
}
