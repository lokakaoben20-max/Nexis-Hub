import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nexis_hub/app_state.dart';
import 'package:nexis_hub/data/demo_repository.dart';
import 'package:nexis_hub/data/models.dart';
import 'package:nexis_hub/data/money.dart';
import 'package:nexis_hub/main.dart';
import 'package:nexis_hub/screens/services_list.dart';

Future<AppState> _home(WidgetTester tester) async {
  tester.view.physicalSize = const Size(1170, 2532);
  tester.view.devicePixelRatio = 3;
  addTearDown(tester.view.reset);
  tester.platformDispatcher.accessibilityFeaturesTestValue =
      const FakeAccessibilityFeatures(disableAnimations: true);
  addTearDown(tester.platformDispatcher.clearAccessibilityFeaturesTestValue);
  final state = AppState(repository: DemoRepository())
    ..setLocale(const Locale('fr'))
    ..signIn();
  await tester.pumpWidget(NexisApp(state: state));
  await tester.pumpAndSettle();
  return state;
}

void main() {
  test('la recherche ignore accents et casse', () {
    expect(foldText('Électricité'), 'electricite');
    expect(foldText('DÉMÉNAGEMENT'), 'demenagement');
  });

  test(
    'sections : récents, nouveaux et recommandés, puis alphabétique',
    () async {
      final all = await DemoRepository().serviceCatalog();
      final s = catalogSections(all);
      expect(s.recents.map((e) => e.id), ['plomberie', 'nettoyage']);
      expect(s.highlights.map((e) => e.id), [
        'electricite',
        'peinture',
        'demenagement',
      ]);
      expect(s.others.first.id, 'climatisation');
      // Aucun service n'est répété.
      final ids = [...s.recents, ...s.highlights, ...s.others].map((e) => e.id);
      expect(ids.toSet().length, all.length);
      // La feuille « + » montre huit services, les récents d'abord.
      final sheet = sheetServices(all);
      expect(sheet.length, 8);
      expect(sheet.first.id, 'plomberie');
    },
  );

  testWidgets('accueil : une carte, bascule CDF/USD, masquage, (i)', (
    tester,
  ) async {
    final state = await _home(tester);
    expect(
      find.text(formatMoney(const Money(45000, Currency.cdf), 'fr')),
      findsOneWidget,
    );
    expect(find.textContaining('bloqués pour vos missions'), findsOneWidget);

    await tester.tap(find.text('USD').first);
    await tester.pumpAndSettle();
    expect(state.walletCurrency.name, 'usd');
    expect(
      find.text(formatMoney(const Money(45000, Currency.cdf), 'fr')),
      findsNothing,
    );

    await tester.tap(find.bySemanticsLabel('Masquer les montants'));
    await tester.pumpAndSettle();
    expect(state.amountsHidden, isTrue);
    expect(find.text('•••• USD'), findsOneWidget);

    await tester.tap(find.bySemanticsLabel('Pourquoi ces fonds sont bloqués'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Cet argent reste à vous'), findsOneWidget);
  });

  testWidgets('« + » : Autre ouvre la liste, la demande libre part', (
    tester,
  ) async {
    await _home(tester);
    await tester.tap(find.bySemanticsLabel('Demander un service'));
    await tester.pumpAndSettle();
    expect(find.text('Quel service ?'), findsOneWidget);
    expect(find.text('Nouveau'), findsOneWidget);
    await tester.tap(find.text('Autre'));
    await tester.pumpAndSettle();
    expect(find.text('Tous les services'), findsWidgets);

    await tester.enterText(find.byType(TextField), 'elec');
    await tester.pumpAndSettle();
    expect(find.text('Électricité'), findsOneWidget);
    expect(find.text('Plomberie'), findsNothing);
    await tester.enterText(find.byType(TextField), 'zzz');
    await tester.pumpAndSettle();
    expect(find.text('Aucun service ne correspond.'), findsOneWidget);

    await tester.scrollUntilVisible(
      find.text('Décrire mon besoin'),
      200,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(find.text('Décrire mon besoin'));
    await tester.pumpAndSettle();
    // Bouton inactif tant que ce n'est pas rempli.
    await tester.tap(find.text('Envoyer ma demande'));
    await tester.pumpAndSettle();
    expect(find.text('Demande envoyée'), findsNothing);

    await tester.enterText(find.byType(TextField).at(0), 'Portail');
    await tester.enterText(
      find.byType(TextField).at(1),
      'Le portail ne ferme plus',
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Envoyer ma demande'));
    await tester.pumpAndSettle();
    expect(find.text('Demande envoyée'), findsOneWidget);
    expect(find.text('Portail'), findsOneWidget);
  });

  testWidgets('le lancement précède la bienvenue', (tester) async {
    tester.view.physicalSize = const Size(1170, 2532);
    tester.view.devicePixelRatio = 3;
    addTearDown(tester.view.reset);
    final state = AppState(repository: DemoRepository())
      ..setLocale(const Locale('fr'));
    await tester.pumpWidget(NexisApp(state: state));
    expect(find.text('Commencer'), findsNothing);
    await tester.pump(const Duration(milliseconds: 2000));
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.text('Commencer'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });

  test('une mission affiche la note du serveur, pas un calcul', () async {
    final repo = DemoRepository();
    final done = (await repo.missions()).firstWhere(
      (m) => m.status == MissionStatus.completed && m.providerName == 'Jean M.',
    );
    expect(done.rating, 4.8);
    expect(done.reviews, 92);
  });
}
