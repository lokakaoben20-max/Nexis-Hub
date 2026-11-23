// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get slogan => 'Where trust meets service.';

  @override
  String get welcomeIntro => 'We connect you with trusted professionals';

  @override
  String get verifiedProvider => 'Verified provider';

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
  String codeSentTo(String channel, String phone) {
    return 'Sent on $channel to $phone.';
  }

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
  String walletLocked(String amount) {
    return '$amount locked for your ongoing jobs';
  }

  @override
  String get walletExplanation =>
      'This money is paid to the provider only after the client confirms the job.';

  @override
  String get walletInfoLabel => 'Why is this amount locked?';

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
  String get viewQuotes => 'View quotes';

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
  String get comingSoonText => 'This screen comes in a next version.';

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

  @override
  String get editProfile => 'Edit';

  @override
  String get pickServiceHint => 'Pick one, we\'ll handle the rest.';

  @override
  String get otherNeed => 'Other';

  @override
  String get close => 'Close';

  @override
  String quotesPill(int count) {
    return '$count quotes';
  }

  @override
  String get waitingPill => 'Waiting';

  @override
  String get legalTerms => 'Terms of use';

  @override
  String get legalPrivacy => 'Privacy policy';

  @override
  String get notReceived => 'Didn\'t get it?';

  @override
  String resendIn(String time) {
    return 'Resend in $time';
  }

  @override
  String get resendNow => 'Resend the code';

  @override
  String get myInfo => 'My details';

  @override
  String get myInfoSub => 'Name, photo, commune';

  @override
  String devicesCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count connected devices',
      one: '1 connected device',
    );
    return '$_temp0';
  }

  @override
  String get helpDisputes => 'Help and disputes';

  @override
  String get helpDisputesSub => 'A problem with a mission';

  @override
  String get spaceClient => 'Client';

  @override
  String get spaceProvider => 'Provider';

  @override
  String get bestRated => 'Top rated';

  @override
  String chooseProvider(String name) {
    return 'Choose $name';
  }

  @override
  String get securedUntilDone =>
      'Your money stays secured by Nexis Hub until you confirm it\'s done.';

  @override
  String get payTitle => 'Pay';

  @override
  String get payWith => 'Pay with';

  @override
  String get addNumber => 'Add a number';

  @override
  String paySecuredNote(String name) {
    return 'Secured by Nexis Hub: $name gets paid when you confirm it\'s done.';
  }

  @override
  String payAmount(String amount) {
    return 'Pay $amount';
  }

  @override
  String get pendingTitle => 'Approve on your phone';

  @override
  String pendingText(String operator, String amount) {
    return '$operator is sending you a request for $amount. Enter your Mobile Money PIN to accept it.';
  }

  @override
  String pendingSent(String operator) {
    return 'Request sent to $operator';
  }

  @override
  String get pendingWaiting => 'Waiting for confirmation';

  @override
  String get pendingWithin => 'You have 5 minutes';

  @override
  String get pendingSecured => 'Money secured by Nexis Hub';

  @override
  String pendingNotify(String name) {
    return '$name is told right away';
  }

  @override
  String get nothingReceived => 'I didn\'t get anything';

  @override
  String get paymentTitle => 'Payment';

  @override
  String get trackTitle => 'Tracking';

  @override
  String distanceAway(String name, String km) {
    return '$name is $km km away';
  }

  @override
  String get trackingOff => 'Tracking not turned on';

  @override
  String get stepPaid => 'Paid';

  @override
  String get stepOnTheWay => 'On the way';

  @override
  String get stepOnTheWaySub => 'Location tracking on';

  @override
  String get stepOnSite => 'On site';

  @override
  String get stepWorkDone => 'Work done';

  @override
  String stepConfirm(String name) {
    return 'You confirm, $name gets paid';
  }

  @override
  String get confirmAction => 'Confirm';

  @override
  String confirmQuestion(String name) {
    return '$name is done.\nIs it done well?';
  }

  @override
  String confirmText(String name) {
    return 'When you confirm, Nexis Hub pays the secured money to $name.';
  }

  @override
  String paidTo(String name) {
    return 'Paid to $name';
  }

  @override
  String get amountFixed => 'Amount set by Nexis Hub at payment';

  @override
  String get report48h =>
      'A problem? You have 48 h to report it. The money then stays blocked while we look into it with you both.';

  @override
  String get yesDone => 'Yes, it\'s done';

  @override
  String get reportProblem => 'Report a problem';

  @override
  String confirmedToast(String name) {
    return 'Thanks! $name gets paid.';
  }

  @override
  String get callLabel => 'Call';

  @override
  String get messageLabel => 'Message';

  @override
  String get whatHappened => 'What happened?';

  @override
  String get reasonNotFinished => 'The work isn\'t finished';

  @override
  String get reasonBadWork => 'The work is poorly done';

  @override
  String get reasonNoShow => 'The provider didn\'t come';

  @override
  String get reasonOther => 'Another problem';

  @override
  String get reportHint => 'Tell us in a few words what\'s wrong.';

  @override
  String get addPhoto => 'Add a photo';

  @override
  String reportFrozen(String amount) {
    return 'The $amount stay on hold while we look into it with you both. Nobody can touch it.';
  }

  @override
  String get sendReport => 'Send the report';

  @override
  String get reportFailed => 'The report wasn\'t sent. Try again in a moment.';

  @override
  String get disputeTitle => 'Dispute';

  @override
  String get nobodyTouches => 'Nobody can touch it';

  @override
  String get youReported => 'You reported it';

  @override
  String photosCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count photos',
      one: '1 photo',
      zero: 'no photo',
    );
    return '$_temp0';
  }

  @override
  String providerReplied(String name) {
    return '$name replied';
  }

  @override
  String get nexisLooking => 'Nexis Hub is looking into it';

  @override
  String get nexisLookingSub => 'Answer within 48 h · we may call you';

  @override
  String get decisionStep => 'Decision and money';

  @override
  String get decisionStepSub => 'Paid out, refunded or split';

  @override
  String settleHint(String name) {
    return 'You can still sort it out with $name. If you both agree, say so here and we close the dispute.';
  }

  @override
  String get writeNexis => 'Write to Nexis Hub';

  @override
  String get weSettled => 'We sorted it out';

  @override
  String get disputeOver => 'Dispute closed';

  @override
  String get outcomeRefundTitle => 'We\'re refunding you';

  @override
  String outcomeRefundText(String name) {
    return 'After reviewing the case and talking with $name, Nexis Hub decided to refund you. The money reaches your wallet in 3 days unless someone contests.';
  }

  @override
  String outcomeReleaseTitle(String name) {
    return 'The money goes to $name';
  }

  @override
  String outcomeReleaseText(String name) {
    return 'After reviewing the case with you both, Nexis Hub decided the money goes to $name. It\'s paid out in 3 days unless someone contests.';
  }

  @override
  String get outcomeSplitTitle => 'The money is split';

  @override
  String outcomeSplitText(String name) {
    return 'After reviewing the case with you both, Nexis Hub decided to split the money between you and $name. Your share reaches your wallet in 3 days unless someone contests.';
  }

  @override
  String get toRefundYou => 'Refund to you';

  @override
  String forProvider(String name) {
    return 'For $name';
  }

  @override
  String blockedDaysLeft(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'On hold (dispute) · $count more days',
      one: 'On hold (dispute) · 1 more day',
    );
    return '$_temp0';
  }

  @override
  String contestHint(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other:
          'Disagree? You have $count days to ask for the decision to be reviewed. The money stays on hold meanwhile.',
      one: 'Disagree? You have 1 more day to ask for the decision to be reviewed. The money stays on hold meanwhile.',
    );
    return '$_temp0';
  }

  @override
  String get seeWallet => 'See my wallet';

  @override
  String get inService => 'On duty';

  @override
  String get offService => 'Off duty';

  @override
  String inServiceSub(String communes) {
    return 'You get requests from $communes';
  }

  @override
  String get offServiceSub => 'You don\'t get new requests';

  @override
  String get offServiceHint =>
      'Turn on “On duty” to get requests from clients.';

  @override
  String andList(String head, String last) {
    return '$head and $last';
  }

  @override
  String securedUntilConfirm(String amount) {
    return '$amount secured, paid out when the client confirms';
  }

  @override
  String get newRequests => 'New requests';

  @override
  String get noRequests => 'No new requests for now.';

  @override
  String get jobsInProgress => 'Ongoing missions';

  @override
  String get newPill => 'New';

  @override
  String minutesAgo(int count) {
    return '$count min';
  }

  @override
  String hoursAgo(int count) {
    return '$count h';
  }

  @override
  String get quoteSentPill => 'Quote sent';

  @override
  String get sendAQuote => 'Send a quote';

  @override
  String get sendTheQuote => 'Send the quote';

  @override
  String get yourPrice => 'Your price';

  @override
  String get priceAsked => 'Amount asked from the client';

  @override
  String get changeCurrency => 'Change currency';

  @override
  String get yourSlot => 'Your time slot';

  @override
  String get otherSlot => 'Other';

  @override
  String get quoteSentToast =>
      'Quote sent. You\'ll be told if the client picks it.';

  @override
  String get quoteFailed => 'The quote wasn\'t sent. Try again in a moment.';

  @override
  String get actionFailed => 'That didn\'t work. Try again in a moment.';

  @override
  String get jobTitle => 'Mission';

  @override
  String get jobToStart => 'Paid, time to set off';

  @override
  String get jobOnTheWay => 'On the way';

  @override
  String jobArrivalPending(String name) {
    return '$name must confirm your arrival';
  }

  @override
  String get jobOnSite => 'On site';

  @override
  String jobWaitingClient(String name) {
    return 'Done, $name must confirm';
  }

  @override
  String get shareLocation => 'Share my location';

  @override
  String shareLocationSub(String name) {
    return '$name sees how far away you are';
  }

  @override
  String get pStepPaid => 'Client paid';

  @override
  String get pStepLeft => 'I set off';

  @override
  String get pStepArrive => 'I arrive on site';

  @override
  String get pStepOnSite => 'I\'m on site';

  @override
  String get pStepDone => 'I\'m done';

  @override
  String get btnLeave => 'I\'m setting off';

  @override
  String get btnArrived => 'I\'ve arrived';

  @override
  String get btnFinished => 'I\'m done';

  @override
  String callClient(String name) {
    return 'Call $name';
  }

  @override
  String arrivalWaiting(String name) {
    return '$name must confirm your arrival on their phone. You can also type their presence code.';
  }

  @override
  String arrivalWaitingSub(String name) {
    return 'Waiting for $name';
  }

  @override
  String get arrivalConfirmed => 'Arrival confirmed';

  @override
  String get presenceCode => 'Client\'s presence code';

  @override
  String get confirmCode => 'Confirm';

  @override
  String wrongCode(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Wrong code. $count tries left.',
      one: 'Wrong code. 1 try left.',
    );
    return '$_temp0';
  }

  @override
  String codeLocked(String name) {
    return 'Too many tries. Only $name can confirm your arrival now.';
  }

  @override
  String finishedNote(String name) {
    return '$name has 48 h to confirm or report a problem. With no answer, the money is paid to you after 48 h.';
  }

  @override
  String get smsSub => 'A text message to this number';

  @override
  String codeSentBySms(String phone) {
    return 'Sent by SMS to $phone.';
  }

  @override
  String get noCodeChannel =>
      'No channel is available right now. Please try again in a moment.';

  @override
  String get numberNotCongolese =>
      'This doesn\'t look like a Congolese number.';

  @override
  String get neverAskCode =>
      'We will never ask for this code by phone or message.';

  @override
  String get enterCode => 'Enter the code';

  @override
  String get codeHint => 'Valid for 10 minutes. Don\'t share it with anyone.';

  @override
  String codeSentToast(String channel) {
    return 'Code sent by $channel.';
  }

  @override
  String codeResentToast(String channel) {
    return 'New code sent by $channel.';
  }

  @override
  String receiveInstead(String channel) {
    return 'Get it by $channel instead';
  }

  @override
  String helloHome(String name) {
    return 'Hello, $name';
  }

  @override
  String heldForMissions(String amount) {
    return '$amount held for your ongoing missions';
  }

  @override
  String get heldWhy => 'Why these funds are held';

  @override
  String get heldTip =>
      'This money is still yours. It is set aside to pay the professional once the mission is done and you have confirmed it.';

  @override
  String get currency => 'Currency';

  @override
  String get quickActions => 'Quick actions';

  @override
  String reviewsCount(int count) {
    return '$count reviews';
  }

  @override
  String completedOn(String date) {
    return 'Completed on $date';
  }

  @override
  String get followMission => 'Follow the mission';

  @override
  String seeMissions(int count) {
    return 'See all $count missions';
  }

  @override
  String get recentMovements => 'Latest movements';

  @override
  String get newBadge => 'New';

  @override
  String get allServices => 'All services';

  @override
  String get searchService => 'Search for a service';

  @override
  String get recents => 'Recent';

  @override
  String get newAndRecommended => 'New and recommended';

  @override
  String requestedIn(String month) {
    return 'Requested in $month';
  }

  @override
  String requestedOn(String date) {
    return 'Requested on $date';
  }

  @override
  String get addedThisWeek => 'Added this week';

  @override
  String get recommendedForYou => 'Recommended for you';

  @override
  String get noServiceMatches => 'No service matches.';

  @override
  String get cantFindService => 'Can\'t find your service?';

  @override
  String get cantFindHint =>
      'Describe your need in your own words, we pass it on to the team.';

  @override
  String get describeNeed => 'Describe my need';

  @override
  String get describeLead =>
      'Tell us what you need in your own words. The Nexis Hub team looks at your request and finds the right professional.';

  @override
  String get describeTypeLabel => 'What kind of service?';

  @override
  String get describeTypeHint => 'For example: gate repair';

  @override
  String get describeTextLabel => 'Describe your need';

  @override
  String get describeTextHint => 'Where, what, and when if it is urgent';

  @override
  String get optional => 'optional';

  @override
  String get photos => 'Photos';

  @override
  String get addShort => 'Add';

  @override
  String get describeNoPay =>
      'You pay nothing at this step. You are notified in the app as soon as we have an answer.';

  @override
  String get sendRequest => 'Send my request';

  @override
  String get requestSent => 'Request sent';

  @override
  String get requestSentText =>
      'We have received your request. You will be notified in the app, and on WhatsApp or Telegram, as soon as we have an answer.';

  @override
  String get backHome => 'Back to home';

  @override
  String get requestNotSent =>
      'The request was not sent. Try again in a moment.';

  @override
  String get notifications => 'Notifications';

  @override
  String get notificationsSub => 'WhatsApp and in the app';

  @override
  String termsVersion(String date) {
    return 'Version of $date';
  }

  @override
  String get securedByNexis => 'Secured by Nexis Hub';
}
