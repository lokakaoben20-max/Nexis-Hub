import 'package:flutter/widgets.dart';

import 'data/money.dart';
import 'data/repository.dart';

/// État partagé de l'app : langue choisie et accès aux données.
class AppState extends ChangeNotifier {
  AppState({required this.repository});

  final NexisRepository repository;
  Locale? _locale;
  bool _signedIn = false;
  bool _serviceHintShown = false;

  /// L'indication du bouton de service ne joue qu'une fois par lancement.
  bool takeServiceHint() {
    if (_serviceHintShown) return false;
    _serviceHintShown = true;
    return true;
  }

  int _revision = 0;

  Locale? get locale => _locale;

  /// Change quand des données changent (paiement, confirmation) : les
  /// écrans relisent alors le dépôt.
  int get revision => _revision;

  void dataChanged() {
    _revision++;
    notifyListeners();
  }

  bool get signedIn => _signedIn;

  Currency _walletCurrency = Currency.cdf;
  bool _amountsHidden = false;

  /// Devise montrée sur la carte du portefeuille (accueil et portefeuille
  /// la partagent) et masquage des montants.
  Currency get walletCurrency => _walletCurrency;
  bool get amountsHidden => _amountsHidden;

  void setWalletCurrency(Currency value) {
    if (value == _walletCurrency) return;
    _walletCurrency = value;
    notifyListeners();
  }

  void setAmountsHidden(bool value) {
    if (value == _amountsHidden) return;
    _amountsHidden = value;
    notifyListeners();
  }

  bool _providerSpace = false;

  /// Espace Prestataire affiché (un même compte peut être client et
  /// prestataire, avec un seul portefeuille).
  bool get providerSpace => _providerSpace;

  void setProviderSpace(bool value) {
    if (value == _providerSpace) return;
    _providerSpace = value;
    notifyListeners();
  }

  void setLocale(Locale locale) {
    _locale = locale;
    notifyListeners();
  }

  void signIn() {
    _signedIn = true;
    notifyListeners();
  }

  void signOut() {
    _signedIn = false;
    _providerSpace = false;
    _amountsHidden = false;
    notifyListeners();
  }
}

class AppScope extends InheritedNotifier<AppState> {
  const AppScope({super.key, required AppState state, required super.child})
    : super(notifier: state);

  static AppState of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<AppScope>()!.notifier!;
}
