import 'package:flutter/widgets.dart';

import 'data/repository.dart';

/// État partagé de l'app : langue choisie et accès aux données.
class AppState extends ChangeNotifier {
  AppState({required this.repository});

  final NexisRepository repository;
  Locale? _locale;
  bool _signedIn = false;

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
    notifyListeners();
  }
}

class AppScope extends InheritedNotifier<AppState> {
  const AppScope({super.key, required AppState state, required super.child})
    : super(notifier: state);

  static AppState of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<AppScope>()!.notifier!;
}
