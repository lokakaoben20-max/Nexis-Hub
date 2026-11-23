import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nexis_hub/app_state.dart';
import 'package:nexis_hub/data/demo_repository.dart';
import 'package:nexis_hub/data/models.dart';
import 'package:nexis_hub/data/money.dart';
import 'package:nexis_hub/main.dart';
import 'package:nexis_hub/screens/services_list.dart';
import 'package:nexis_hub/ui/nx_parts.dart';
import 'package:nexis_hub/ui/theme.dart';

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

  testWidgets('« + » : le catalogue s’ouvre et la demande libre part', (
    tester,
  ) async {
    await _home(tester);
    await tester.tap(find.bySemanticsLabel('Demander un service'));
    await tester.pumpAndSettle();
    expect(find.text('Quel service ?'), findsOneWidget);
    expect(find.text('Nouveau'), findsOneWidget);
    await tester.tap(find.bySemanticsLabel('Tous les services'));
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

  testWidgets('les services partagent leur palette en clair et en sombre', (
    tester,
  ) async {
    final dispatcher = tester.platformDispatcher;
    dispatcher.platformBrightnessTestValue = Brightness.light;
    addTearDown(dispatcher.clearPlatformBrightnessTestValue);
    await _home(tester);
    await tester.tap(find.bySemanticsLabel('Demander un service'));
    await tester.pumpAndSettle();

    OutlinedButton button(String label) =>
        tester.widget(find.widgetWithText(OutlinedButton, label));
    Container tile(String label) => tester.widget(
      find.descendant(
        of: find.widgetWithText(OutlinedButton, label),
        matching: find.descendant(
          of: find.byType(ServiceTile),
          matching: find.byType(Container),
        ),
      ),
    );

    for (final label in ['Plomberie', 'Électricité', 'Nettoyage']) {
      expect(
        (tile(label).decoration! as BoxDecoration).color,
        const Color(0xFFEDF2FA),
      );
      expect(
        (tile(label).child! as ExcludeSemantics).child,
        isA<Icon>().having(
          (icon) => icon.color,
          'pictogramme',
          NexisColors.navy,
        ),
      );
    }
    expect(
      button('Plomberie').style!.side!.resolve({WidgetState.focused})!.color,
      NexisColors.brand,
    );

    dispatcher.platformBrightnessTestValue = Brightness.dark;
    await tester.pumpAndSettle();
    expect(
      (tile('Plomberie').decoration! as BoxDecoration).color,
      NexisPalette.dark.soft,
    );
    expect(
      (tile('Plomberie').child! as ExcludeSemantics).child,
      isA<Icon>().having(
        (icon) => icon.color,
        'pictogramme sombre',
        NexisPalette.dark.ink,
      ),
    );
  });

  testWidgets('le catalogue suit la langue et recherche les noms traduits', (
    tester,
  ) async {
    final state = await _home(tester);
    state.setLocale(const Locale('en'));
    await tester.pumpAndSettle();

    await tester.tap(find.bySemanticsLabel('Request a service'));
    await tester.pumpAndSettle();
    expect(find.bySemanticsLabel('Plumbing'), findsOneWidget);
    expect(find.bySemanticsLabel('Painting'), findsOneWidget);
    await tester.tap(find.bySemanticsLabel('All services'));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField), 'moving');
    await tester.pumpAndSettle();
    expect(find.text('Moving'), findsOneWidget);
    expect(find.text('Déménagement'), findsNothing);
    await tester.enterText(find.byType(TextField), 'demenag');
    await tester.pumpAndSettle();
    expect(find.text('Moving'), findsOneWidget);
  });

  testWidgets('la carte de devis indique une seule fois le nombre', (
    tester,
  ) async {
    await _home(tester);
    expect(find.text('3 devis reçus'), findsOneWidget);
    expect(find.text('3 devis'), findsNothing);
    await tester.tap(find.text('Voir les devis'));
    await tester.pumpAndSettle();
    expect(find.text('Comparer les devis'), findsOneWidget);
  });

  testWidgets('le bouton plus pulse trois fois au premier accueil', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1170, 2532);
    tester.view.devicePixelRatio = 3;
    addTearDown(tester.view.reset);
    final state = AppState(repository: DemoRepository())
      ..setLocale(const Locale('fr'))
      ..signIn();
    await tester.pumpWidget(NexisApp(state: state));
    await tester.pump(const Duration(seconds: 2));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 420));

    double scale() => tester
        .widget<ScaleTransition>(
          find.descendant(
            of: find.bySemanticsLabel('Demander un service'),
            matching: find.byType(ScaleTransition),
          ),
        )
        .scale
        .value;

    expect(scale(), 1);
    await tester.pump(const Duration(milliseconds: 410)); // 830 ms
    expect(scale(), greaterThan(1.15));
    await tester.pump(const Duration(milliseconds: 390)); // 1220 ms
    expect(scale(), 1);
    await tester.pump(const Duration(milliseconds: 260)); // 1480 ms
    expect(scale(), greaterThan(1.15));
    await tester.pump(const Duration(milliseconds: 390)); // 1870 ms
    expect(scale(), 1);
    await tester.pump(const Duration(milliseconds: 325)); // 2195 ms
    expect(scale(), greaterThan(1.15));
    await tester.pumpAndSettle();
    expect(scale(), 1);
    await tester.tap(find.bySemanticsLabel('Missions'));
    await tester.pumpAndSettle();
    await tester.tap(find.bySemanticsLabel('Accueil'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 950));
    expect(scale(), 1);
    await tester.pumpAndSettle();
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
