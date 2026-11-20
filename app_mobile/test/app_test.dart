import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nexis_hub/app_state.dart';
import 'package:nexis_hub/data/demo_repository.dart';
import 'package:nexis_hub/main.dart';

void main() {
  testWidgets('bienvenue, numéro, code, puis accueil', (tester) async {
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

    await tester.tap(find.text('Commencer'));
    await tester.pumpAndSettle();
    expect(find.text('Ton numéro'), findsOneWidget);
    await tester.enterText(find.byType(TextField), '812345412');
    await tester.pump();
    await tester.tap(find.text('Recevoir le code'));
    await tester.pumpAndSettle();
    expect(find.text('Le code'), findsOneWidget);

    await tester.enterText(find.byType(TextField), '123456');
    await tester.pump(const Duration(milliseconds: 300));
    await tester.pumpAndSettle();
    expect(state.signedIn, isTrue);
    expect(find.text('Bonjour, Grâce'), findsOneWidget);
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
    expect(find.text('Boyei malamu'), findsOneWidget);
    expect(find.text('Ndako'), findsOneWidget);
  });
}
