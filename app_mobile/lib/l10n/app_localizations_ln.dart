// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Lingala (`ln`).
class AppLocalizationsLn extends AppLocalizations {
  AppLocalizationsLn([String locale = 'ln']) : super(locale);

  @override
  String get slogan => 'Epai bosembo ekutani na mosala.';

  @override
  String get welcomeIntro => 'Tokokutanisa bino na basali ya kotyela motema';

  @override
  String get verifiedProvider => 'Mosali vérifié';

  @override
  String get start => 'Kobanda';

  @override
  String get haveAccount => 'Nazali na compte';

  @override
  String get signInTitle => 'Kɔtá na compte na yo';

  @override
  String get noAccountTitle => 'Compte moko te ezwami';

  @override
  String get noAccountHint =>
      'Talá nimero oyo okotisi to salá profil na nimero oyo.';

  @override
  String get changeLoginNumber => 'Bongolá nimero';

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
  String codeSentTo(String channel, String phone) {
    return 'Etindami na $channel na $phone.';
  }

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
  String walletLocked(String amount) {
    return '$amount ekangami mpo na misala na yo oyo ezali kosalema';
  }

  @override
  String get walletExplanation =>
      'Mbongo oyo ekopesama na mosali kaka sima ya kondimama na mosombi.';

  @override
  String get walletInfoLabel => 'Mpo na nini mbongo oyo ekangami?';

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
  String get firstRequestTitle => 'Ozali na mposa ya mosala nini ?';

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
  String get statusDisputed => 'Matata ezali kotalelama';

  @override
  String get compareQuotes => 'Kokokanisa ba devis';

  @override
  String get viewQuotes => 'Kotala ba devis';

  @override
  String get follow => 'Kolanda';

  @override
  String get paySecured => 'Ebatelami na Nexis Hub';

  @override
  String get payReleased => 'Epesami na mosali';

  @override
  String get payRefunded => 'Bazongisi';

  @override
  String get payBlocked => 'Ekangami (matata)';

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

  @override
  String quotesPill(int count) {
    return 'Devis $count';
  }

  @override
  String get waitingPill => 'Ezali kozela';

  @override
  String get legalTerms => 'Mibeko ya kosalela';

  @override
  String get legalPrivacy => 'Politiki ya kobomba sango';

  @override
  String get notReceived => 'Ozwi te ?';

  @override
  String resendIn(String time) {
    return 'Kotinda lisusu na $time';
  }

  @override
  String get resendNow => 'Tinda code lisusu';

  @override
  String get myInfo => 'Makambo na ngai';

  @override
  String get myInfoSub => 'Nkombo, foto, commune';

  @override
  String devicesCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Ba appareils $count ekangami',
      one: 'Appareil 1 ekangami',
    );
    return '$_temp0';
  }

  @override
  String get helpDisputes => 'Lisalisi mpe matata';

  @override
  String get helpDisputesSub => 'Likambo na mosala moko';

  @override
  String get spaceClient => 'Mosombi';

  @override
  String get spaceProvider => 'Mosali';

  @override
  String get bestRated => 'Oyo balingi mingi';

  @override
  String chooseProvider(String name) {
    return 'Pona $name';
  }

  @override
  String get securedUntilDone =>
      'Mbongo na yo ebatelami na Nexis Hub kino okondima ete mosala esili.';

  @override
  String get payTitle => 'Kofuta';

  @override
  String get payWith => 'Futa na';

  @override
  String get addNumber => 'Bakisa nimero';

  @override
  String paySecuredNote(String name) {
    return 'Ebatelami na Nexis Hub : $name akozwa mbongo soki ondimi ete mosala esili.';
  }

  @override
  String payAmount(String amount) {
    return 'Futa $amount';
  }

  @override
  String get pendingTitle => 'Ndima na telefone na yo';

  @override
  String pendingText(String operator, String amount) {
    return '$operator ekotindela yo bosenga ya $amount. Kotisa code na yo ya sekele ya Mobile Money mpo na kondima.';
  }

  @override
  String pendingSent(String operator) {
    return 'Bosenga etindami na $operator';
  }

  @override
  String get pendingWaiting => 'Tozali kozela bondimi';

  @override
  String get pendingWithin => 'Ozali na miniti 5';

  @override
  String get pendingSecured => 'Mbongo ebatelami na Nexis Hub';

  @override
  String pendingNotify(String name) {
    return 'Tokoyebisa $name noki';
  }

  @override
  String get nothingReceived => 'Nazwi eloko te';

  @override
  String get paymentTitle => 'Kofuta';

  @override
  String get trackTitle => 'Kolanda';

  @override
  String distanceAway(String name, String km) {
    return '$name azali na $km km';
  }

  @override
  String get trackingOff => 'Kolanda ebandi te';

  @override
  String get stepPaid => 'Efutami';

  @override
  String get stepOnTheWay => 'Azali na nzela';

  @override
  String get stepOnTheWaySub => 'Kolanda esika ebandi';

  @override
  String get stepOnSite => 'Akomi';

  @override
  String get stepWorkDone => 'Mosala esili';

  @override
  String stepConfirm(String name) {
    return 'Ondimi, $name akozwa mbongo';
  }

  @override
  String get confirmAction => 'Kondima';

  @override
  String confirmQuestion(String name) {
    return '$name asilisi.\nEsalami malamu ?';
  }

  @override
  String confirmText(String name) {
    return 'Soki ondimi, Nexis Hub akopesa $name mbongo oyo ebatelami.';
  }

  @override
  String paidTo(String name) {
    return 'Ekopesama na $name';
  }

  @override
  String get amountFixed => 'Motango etiamaki na Nexis Hub na tango ya kofuta';

  @override
  String get report48h =>
      'Mokakatano ? Ozali na 48 h mpo na koyebisa yango. Mbongo ekotikala ekangami tango tozali kotala yango na bino mibale.';

  @override
  String get yesDone => 'Ee, esili';

  @override
  String get reportProblem => 'Koyebisa mokakatano';

  @override
  String confirmedToast(String name) {
    return 'Matondo ! $name akozwa mbongo.';
  }

  @override
  String get callLabel => 'Kobenga';

  @override
  String get messageLabel => 'Kokoma';

  @override
  String get whatHappened => 'Nini esalemaki ?';

  @override
  String get reasonNotFinished => 'Mosala esili te';

  @override
  String get reasonBadWork => 'Mosala esalemi malamu te';

  @override
  String get reasonNoShow => 'Mosali ayaki te';

  @override
  String get reasonOther => 'Mokakatano mosusu';

  @override
  String get reportHint => 'Yebisa na maloba moke nini ezali malamu te.';

  @override
  String get addPhoto => 'Bakisa elilingi';

  @override
  String reportFrozen(String amount) {
    return '$amount ekokangama tango tozali kotala yango na bino mibale. Moto moko te akoki kosimba yango.';
  }

  @override
  String get sendReport => 'Tinda bosengi';

  @override
  String get reportFailed => 'Bosengi ekendeki te. Meka lisusu mwa moke.';

  @override
  String get disputeTitle => 'Matata';

  @override
  String get nobodyTouches => 'Moto moko te akoki kosimba yango';

  @override
  String get youReported => 'Oyebisaki';

  @override
  String photosCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'bililingi $count',
      one: 'elilingi 1',
      zero: 'elilingi te',
    );
    return '$_temp0';
  }

  @override
  String providerReplied(String name) {
    return '$name azongisaki';
  }

  @override
  String get nexisLooking => 'Nexis Hub azali kotala';

  @override
  String get nexisLookingSub => 'Eyano nakati ya 48 h · tokoki kobenga bino';

  @override
  String get decisionStep => 'Mokano mpe mbongo';

  @override
  String get decisionStepSub => 'Epesami, ezongisami to ekabolami';

  @override
  String settleHint(String name) {
    return 'Okoki naino koyokana na $name. Soki boyokani, yebisa awa mpe tokosilisa matata.';
  }

  @override
  String get writeNexis => 'Komela Nexis Hub';

  @override
  String get weSettled => 'Toyokani';

  @override
  String get disputeOver => 'Matata esili';

  @override
  String get outcomeRefundTitle => 'Tokozongisela yo mbongo';

  @override
  String outcomeRefundText(String name) {
    return 'Sima ya kotala likambo mpe kosolola na $name, Nexis Hub azwi mokano ya kozongisela yo mbongo. Mbongo ekokota na esika ya mbongo na yo nsima ya mikolo 3 soki moto moko te atelemeli.';
  }

  @override
  String outcomeReleaseTitle(String name) {
    return 'Mbongo ekokende epai ya $name';
  }

  @override
  String outcomeReleaseText(String name) {
    return 'Sima ya kotala likambo na bino mibale, Nexis Hub azwi mokano ete mbongo ezali ya $name. Ekokende nsima ya mikolo 3 soki moto moko te atelemeli.';
  }

  @override
  String get outcomeSplitTitle => 'Mbongo ekabolami';

  @override
  String outcomeSplitText(String name) {
    return 'Sima ya kotala likambo na bino mibale, Nexis Hub azwi mokano ya kokabola mbongo kati na yo mpe $name. Eteni na yo ekokota na esika ya mbongo na yo nsima ya mikolo 3 soki moto moko te atelemeli.';
  }

  @override
  String get toRefundYou => 'Ya kozongisela yo';

  @override
  String forProvider(String name) {
    return 'Mpo na $name';
  }

  @override
  String blockedDaysLeft(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Ekangami (matata) · mikolo $count etikali',
      one: 'Ekangami (matata) · mokolo 1 etikali',
    );
    return '$_temp0';
  }

  @override
  String contestHint(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other:
          'Oyokani te ? Ozali na mikolo $count mpo na kotelemela mokano. Mbongo ekotikala ekangami na tango yango.',
      one: 'Oyokani te ? Otikali na mokolo 1 mpo na kotelemela mokano. Mbongo ekotikala ekangami na tango yango.',
    );
    return '$_temp0';
  }

  @override
  String get seeWallet => 'Tala esika ya mbongo na ngai';

  @override
  String get inService => 'Nazali na mosala';

  @override
  String get offService => 'Nazali na mosala te';

  @override
  String inServiceSub(String communes) {
    return 'Ozali kozwa bosengi ya $communes';
  }

  @override
  String get offServiceSub => 'Ozali kozwa bosengi ya sika te';

  @override
  String get offServiceHint =>
      'Fungola « Nazali na mosala » mpo na kozwa bosengi ya basombi.';

  @override
  String andList(String head, String last) {
    return '$head mpe $last';
  }

  @override
  String securedUntilConfirm(String amount) {
    return '$amount ebatelami, ekopesama soki mosombi andimi';
  }

  @override
  String get newRequests => 'Bosengi ya sika';

  @override
  String get noRequests => 'Bosengi ya sika ezali te sikoyo.';

  @override
  String get jobsInProgress => 'Ba mission oyo ezali kosalema';

  @override
  String get newPill => 'Ya sika';

  @override
  String minutesAgo(int count) {
    return '$count min';
  }

  @override
  String hoursAgo(int count) {
    return '$count h';
  }

  @override
  String get quoteSentPill => 'Devis etindami';

  @override
  String get sendAQuote => 'Tinda devis';

  @override
  String get sendTheQuote => 'Tinda devis';

  @override
  String get yourPrice => 'Ntalo na yo';

  @override
  String get priceAsked => 'Mbongo osengi na mosombi';

  @override
  String get changeCurrency => 'Bongola lolenge ya mbongo';

  @override
  String get yourSlot => 'Ngonga na yo';

  @override
  String get otherSlot => 'Mosusu';

  @override
  String get quoteSentToast =>
      'Devis etindami. Tokoyebisa yo soki mosombi aponi yango.';

  @override
  String get quoteFailed => 'Devis ekendeki te. Meka lisusu mwa moke.';

  @override
  String get actionFailed => 'Ebimi malamu te. Meka lisusu mwa moke.';

  @override
  String get jobTitle => 'Mission';

  @override
  String get jobToStart => 'Efutami, kende sikoyo';

  @override
  String get jobOnTheWay => 'Na nzela';

  @override
  String jobArrivalPending(String name) {
    return '$name asengeli kondima ete okomi';
  }

  @override
  String get jobOnSite => 'Na esika';

  @override
  String jobWaitingClient(String name) {
    return 'Esili, $name asengeli kondima';
  }

  @override
  String get shareLocation => 'Kabola esika nazali';

  @override
  String shareLocationSub(String name) {
    return '$name akomona ntaka tii okokoma';
  }

  @override
  String get pStepPaid => 'Mosombi afuti';

  @override
  String get pStepLeft => 'Nabimi';

  @override
  String get pStepArrive => 'Nakokoma na esika';

  @override
  String get pStepOnSite => 'Nazali na esika';

  @override
  String get pStepDone => 'Nasilisi';

  @override
  String get btnLeave => 'Nabimi';

  @override
  String get btnArrived => 'Nakomi';

  @override
  String get btnFinished => 'Nasilisi';

  @override
  String callClient(String name) {
    return 'Benga $name';
  }

  @override
  String arrivalWaiting(String name) {
    return '$name asengeli kondima na telefone na ye ete okomi. Okoki mpe kokotisa code na ye ya bozali.';
  }

  @override
  String arrivalWaitingSub(String name) {
    return 'Tozali kozela $name';
  }

  @override
  String get arrivalConfirmed => 'Bokomi endimami';

  @override
  String get presenceCode => 'Code ya bozali ya mosombi';

  @override
  String get confirmCode => 'Ndima';

  @override
  String wrongCode(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Code ezali malamu te. Meka mbala $count lisusu.',
      one: 'Code ezali malamu te. Meka mbala 1 lisusu.',
    );
    return '$_temp0';
  }

  @override
  String codeLocked(String name) {
    return 'Omeki mingi. Kaka $name akoki sikoyo kondima ete okomi.';
  }

  @override
  String finishedNote(String name) {
    return '$name azali na 48 h mpo na kondima to koyebisa mokakatano. Soki azongisi te, okozwa mbongo nsima ya 48 h.';
  }

  @override
  String get smsSub => 'Message na nimero oyo';

  @override
  String codeSentBySms(String phone) {
    return 'Etindami na SMS na $phone.';
  }

  @override
  String get noCodeChannel =>
      'Nzela moko te ezali sikoyo. Meka lisusu na mwa ntango moke.';

  @override
  String get numberNotCongolese =>
      'Nimero oyo emonani lokola nimero ya Kongó te.';

  @override
  String get neverAskCode =>
      'Tokosenga code oyo na telefone to na message soki moke te.';

  @override
  String get enterCode => 'Tya code';

  @override
  String get codeHint =>
      'Ezali malamu mpo na miniti 10. Kopesa yango na moto moko te.';

  @override
  String codeSentToast(String channel) {
    return 'Code etindami na $channel.';
  }

  @override
  String codeResentToast(String channel) {
    return 'Code ya sika etindami na $channel.';
  }

  @override
  String receiveInstead(String channel) {
    return 'Kozwa na $channel na esika';
  }

  @override
  String eveningHome(String name) {
    return 'Mbote, $name';
  }

  @override
  String helloHome(String name) {
    return 'Mbote, $name';
  }

  @override
  String heldForMissions(String amount) {
    return '$amount ebombami mpo na misala na yo ezali kokende';
  }

  @override
  String get heldWhy => 'Mpo na nini mbongo oyo ebombami';

  @override
  String get heldTip =>
      'Mbongo oyo ezali naino ya yo. Ebombami mpo na kofuta mosali tango mosala esili mpe ondimi yango.';

  @override
  String get currency => 'Mbongo';

  @override
  String get quickActions => 'Misala ya noki';

  @override
  String reviewsCount(int count) {
    return '$count makanisi';
  }

  @override
  String completedOn(String date) {
    return 'Esili na $date';
  }

  @override
  String get followMission => 'Landa mosala';

  @override
  String seeMissions(int count) {
    return 'Tala misala $count';
  }

  @override
  String get recentMovements => 'Makambo ya nsuka ya mbongo';

  @override
  String get newBadge => 'Ya sika';

  @override
  String get allServices => 'Misala nyonso';

  @override
  String get searchService => 'Luka mosala';

  @override
  String get recents => 'Ya nsuka';

  @override
  String get newAndRecommended => 'Ya sika mpe oyo tolobi';

  @override
  String requestedIn(String month) {
    return 'Osengaki na $month';
  }

  @override
  String requestedOn(String date) {
    return 'Osengaki na $date';
  }

  @override
  String get addedThisWeek => 'Etondisami poso oyo';

  @override
  String get recommendedForYou => 'Tozali kopesa yo yango';

  @override
  String get noServiceMatches => 'Mosala moko te ekokani.';

  @override
  String get cantFindService => 'Ozwi mosala na yo te?';

  @override
  String get cantFindHint =>
      'Limbola bosengi na yo na maloba na yo, tokopesa yango na ekipi.';

  @override
  String get serviceRequestDemo => 'Bosengi oyo ezali ya komeka.';

  @override
  String get serviceRequestNoPay => 'Okofuta eloko te na etape oyo.';

  @override
  String get serviceRequestSaved => 'Bosengi ya komeka ebombami';

  @override
  String get serviceRequestSavedText =>
      'Okokuta yango na Misala na ngai, na kati ya misala oyo ezali kozela devis.';

  @override
  String get describeNeed => 'Limbola bosengi na ngai';

  @override
  String get describeLead =>
      'Loba na biso oyo osengi na maloba na yo. Ekipi ya Nexis Hub ekotala bosengi na yo mpe ekoluka mosali malamu.';

  @override
  String get describeTypeLabel => 'Mosala ya lolenge nini?';

  @override
  String get describeTypeHint => 'Ndakisa : kobongisa porte';

  @override
  String get describeTextLabel => 'Limbola bosengi na yo';

  @override
  String get describeTextHint =>
      'Wapi, nini, mpe ntango nini soki ezali lombangu';

  @override
  String get optional => 'ezali ntina te';

  @override
  String get photos => 'Bafoto';

  @override
  String get addShort => 'Bakisa';

  @override
  String get describeNoPay =>
      'Ofutaka eloko te na etape oyo. Tokoyebisa yo na app tango tozwi eyano.';

  @override
  String get sendRequest => 'Tinda bosengi na ngai';

  @override
  String get requestSent => 'Bosengi etindami';

  @override
  String get requestSentText =>
      'Tozwi bosengi na yo. Tokoyebisa yo na app, mpe na WhatsApp to Telegram, tango tozwi eyano.';

  @override
  String get backHome => 'Zonga na ebandeli';

  @override
  String get requestNotSent =>
      'Bosengi etindami te. Meka lisusu na mwa ntango.';

  @override
  String get notifications => 'Ba notifications';

  @override
  String get notificationsSub => 'WhatsApp mpe na app';

  @override
  String termsVersion(String date) {
    return 'Version ya $date';
  }

  @override
  String get securedByNexis => 'Ebombami na Nexis Hub';

  @override
  String get signupTitle => 'Tóyebana';

  @override
  String get signupFirstName => 'Nkombo ya liboso';

  @override
  String get signupLastName => 'Nkombo ya libota';

  @override
  String get signupOtherCommune => 'Komini mosusu';

  @override
  String get signupDemoNotice =>
      'Komikomisa ya komeka. Salelá ba sango ya ndakisa.';

  @override
  String get signupReadTerms => 'Tángá mibeko ya kosalela app';

  @override
  String get signupAcceptTerms => 'Natángi mpe nandimi mibeko ya kosalela app';

  @override
  String get signupCreateProfile => 'Salá profil na ngai';

  @override
  String get signupFailed =>
      'Profil esalemi te. Talá sango na yo mpe mekisa lisusu.';

  @override
  String get signupDemoTerms =>
      'Mokanda ya komeka. Awa okoki komeka kotánga mpe kondima mibeko. Ba profil, misala mpe mbongo na aperçu oyo ezali ya ndakisa. Sango ya komikomisa elongwaka ntango app efungwami lisusu.';
}
