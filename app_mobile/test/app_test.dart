import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nexis_hub/app_state.dart';
import 'package:nexis_hub/data/demo_repository.dart';
import 'package:nexis_hub/l10n/app_localizations_fr.dart';
import 'package:nexis_hub/main.dart';
import 'package:nexis_hub/screens/home.dart';
import 'package:nexis_hub/ui/common.dart';

void main() {
  test('la salutation française change à midi', () {
    final l = AppLocalizationsFr();
    expect(
      homeGreeting(l, 'Amina', DateTime(2026, 11, 23, 11, 59)),
      'Bonjour, Amina',
    );
    expect(
      homeGreeting(l, 'Amina', DateTime(2026, 11, 23, 12)),
      'Bonsoir, Amina',
    );
  });

  testWidgets('un compte existant ouvre directement son accueil', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1170, 2532);
    tester.view.devicePixelRatio = 3;
    addTearDown(tester.view.reset);
    // L'écran de bienvenue tourne en boucle : ici, comme un téléphone qui
    // demande moins d'animations, tout s'affiche directement.
    tester.platformDispatcher.accessibilityFeaturesTestValue =
        const FakeAccessibilityFeatures(disableAnimations: true);
    addTearDown(tester.platformDispatcher.clearAccessibilityFeaturesTestValue);
    final state = AppState(repository: DemoRepository())
      ..setLocale(const Locale('fr'));
    await tester.pumpWidget(NexisApp(state: state));
    await tester.pumpAndSettle();
    expect(find.text('Commencer'), findsOneWidget);

    await tester.tap(find.text("J'ai déjà un compte"));
    await tester.pumpAndSettle();
    expect(find.text('Votre numéro'), findsOneWidget);
    await tester.enterText(find.byType(TextField), '812345412');
    await tester.pump();
    await tester.tap(find.text('Recevoir le code'));
    await tester.pumpAndSettle();
    expect(find.text('Entrez le code'), findsOneWidget);

    await tester.enterText(find.byType(TextField), '123456');
    await tester.pump(const Duration(milliseconds: 300));
    await tester.pumpAndSettle();
    expect(state.signedIn, isTrue);
    expect(
      find.text(homeGreeting(AppLocalizationsFr(), 'Grâce', DateTime.now())),
      findsOneWidget,
    );
    expect(find.text('De quoi avez-vous besoin ?'), findsNothing);
  });

  testWidgets('un nouveau client doit remplir le profil et accepter les CGU', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1170, 2532);
    tester.view.devicePixelRatio = 3;
    addTearDown(tester.view.reset);
    tester.platformDispatcher.accessibilityFeaturesTestValue =
        const FakeAccessibilityFeatures(disableAnimations: true);
    addTearDown(tester.platformDispatcher.clearAccessibilityFeaturesTestValue);

    final repo = DemoRepository();
    final state = AppState(repository: repo)..setLocale(const Locale('fr'));
    await tester.pumpWidget(NexisApp(state: state));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Commencer'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), '812345678');
    await tester.pump();
    await tester.tap(find.text('Recevoir le code'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), '123456');
    await tester.pump(const Duration(milliseconds: 300));
    await tester.pumpAndSettle();

    expect(find.text('Faisons connaissance'), findsOneWidget);
    expect(state.signedIn, isFalse);
    await tester.enterText(find.byType(TextField).at(0), '  Amina ');
    await tester.enterText(find.byType(TextField).at(1), ' Lemba  ');
    await tester.tap(find.text('Commune'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Gombe').last);
    await tester.pumpAndSettle();

    await tester.tap(find.text('Créer mon profil'), warnIfMissed: false);
    await tester.pumpAndSettle();
    expect(state.signedIn, isFalse);
    expect(repo.openDemoAccount('+243812345678'), isFalse);

    await tester.ensureVisible(find.text('Lire les CGU'));
    await tester.tap(find.text('Lire les CGU'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Document de démonstration.'), findsOneWidget);
    await tester.tap(find.byType(RoundBack));
    await tester.pumpAndSettle();
    expect(
      tester.widget<CheckboxListTile>(find.byType(CheckboxListTile)).value,
      isFalse,
    );

    await tester.ensureVisible(find.byType(CheckboxListTile));
    await tester.tap(find.byType(CheckboxListTile));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Créer mon profil'));
    await tester.pumpAndSettle();

    expect(state.signedIn, isTrue);
    expect(
      find.text(homeGreeting(AppLocalizationsFr(), 'Amina', DateTime.now())),
      findsOneWidget,
    );
    expect(find.text('De quoi avez-vous besoin ?'), findsOneWidget);
    expect(find.text('Terminées'), findsNothing);
    final home = find.byType(HomeScreen);
    final bottom =
        tester.getBottomLeft(home).dy -
        tester.widget<HomeScreen>(home).bottomInset;
    final top = tester
        .getBottomLeft(find.bySemanticsLabel('Actions rapides'))
        .dy;
    final heading = find.text('De quoi avez-vous besoin ?');
    final requestButton = find.widgetWithText(
      FilledButton,
      'Demander un service',
    );
    final blockCenter =
        (tester.getTopLeft(heading).dy +
            tester.getBottomRight(requestButton).dy) /
        2;
    expect(blockCenter, closeTo((top + bottom) / 2, 1));
    await tester.tap(requestButton);
    await tester.pumpAndSettle();
    expect(find.bySemanticsLabel('Fermer'), findsOneWidget);
    expect(find.text('Quel service ?'), findsOneWidget);
    expect(find.bySemanticsLabel('Tous les services'), findsOneWidget);
    final profile = await repo.profile();
    expect(profile.lastName, 'Lemba');
    expect(profile.commune, 'Gombe');
    expect(profile.termsVersion, repo.signupTermsVersion);
    expect(profile.isProvider, isFalse);
    expect(await repo.missions(), isEmpty);
    expect(await repo.movements(), isEmpty);
    expect((await repo.wallet()).available, isEmpty);
    expect(repo.openDemoAccount('+243812345412'), isTrue);
    expect((await repo.profile()).firstName, 'Grâce');
    expect(repo.openDemoAccount('+243812345678'), isTrue);
    expect((await repo.profile()).firstName, 'Amina');
  });

  testWidgets('numéro : mise en forme, préfixe contrôlé, bouton grisé', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1170, 2532);
    tester.view.devicePixelRatio = 3;
    addTearDown(tester.view.reset);
    tester.platformDispatcher.accessibilityFeaturesTestValue =
        const FakeAccessibilityFeatures(disableAnimations: true);
    addTearDown(tester.platformDispatcher.clearAccessibilityFeaturesTestValue);
    final state = AppState(repository: DemoRepository())
      ..setLocale(const Locale('fr'));
    await tester.pumpWidget(NexisApp(state: state));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Commencer'));
    await tester.pumpAndSettle();

    TextField field() => tester.widget<TextField>(find.byType(TextField));
    // Le bouton est inactif tant que le numéro n'est pas valide.
    bool enabled() =>
        tester
            .widget<InkWell>(
              find.ancestor(
                of: find.text('Recevoir le code'),
                matching: find.byType(InkWell),
              ),
            )
            .onTap !=
        null;

    expect(find.text('WhatsApp'), findsOneWidget);
    expect(find.text('Telegram'), findsOneWidget);
    expect(find.text('SMS'), findsOneWidget);
    expect(find.byType(Image), findsNothing); // pas de logos, comme la maquette
    expect(enabled(), isFalse);

    await tester.enterText(find.byType(TextField), '81234');
    await tester.pump();
    expect(field().controller!.text, '81 234');
    expect(enabled(), isFalse); // incomplet

    await tester.enterText(find.byType(TextField), '70 234 5678');
    await tester.pump();
    expect(
      find.text('Ce numéro ne semble pas être un numéro congolais.'),
      findsOneWidget,
    );
    expect(enabled(), isFalse);

    await tester.enterText(find.byType(TextField), '0812345678');
    await tester.pump();
    expect(field().controller!.text, '81 234 5678');
    expect(enabled(), isTrue);
  });

  testWidgets('la pastille de langue ouvre un menu des trois langues', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1170, 2532);
    tester.view.devicePixelRatio = 3;
    addTearDown(tester.view.reset);
    final state = AppState(repository: DemoRepository())
      ..setLocale(const Locale('fr'));
    await tester.pumpWidget(NexisApp(state: state));
    await tester.pump(const Duration(seconds: 2));
    expect(find.text('Commencer'), findsOneWidget);

    await tester.tap(find.text('FR'));
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
    expect(find.text('Français'), findsOneWidget);
    expect(find.text('Lingala'), findsOneWidget);
    expect(find.text('English'), findsOneWidget);
    expect(state.locale?.languageCode, 'fr');

    await tester.tap(find.text('English'));
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
    expect(state.locale?.languageCode, 'en');
    expect(find.text('Lingala'), findsNothing);
    expect(find.text('Get started'), findsOneWidget);
    // Quitter l'écran arrête les animations et les minuteries.
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('le lingala change les textes de l\'app', (tester) async {
    tester.view.physicalSize = const Size(1170, 2532);
    tester.view.devicePixelRatio = 3;
    addTearDown(tester.view.reset);
    final state = AppState(repository: DemoRepository())..signIn();
    await tester.pumpWidget(NexisApp(state: state));
    await tester.pumpAndSettle();
    state.setLocale(const Locale('ln'));
    await tester.pumpAndSettle();
    expect(find.textContaining('ebombami'), findsOneWidget);
    expect(find.text('Ndako'), findsOneWidget);
    expect(find.text('Mbote, Grâce'), findsOneWidget);
  });
}
