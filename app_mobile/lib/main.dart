import 'package:flutter/material.dart';

import 'app_state.dart';
import 'data/demo_repository.dart';
import 'l10n/app_localizations.dart';
import 'screens/launch.dart';
import 'screens/shell.dart';
import 'screens/welcome.dart';
import 'ui/lingala_fallback.dart';
import 'ui/theme.dart';

void main() {
  runApp(NexisApp(state: AppState(repository: DemoRepository())));
}

class NexisApp extends StatelessWidget {
  const NexisApp({super.key, required this.state});

  final AppState state;

  @override
  Widget build(BuildContext context) {
    return AppScope(
      state: state,
      child: ListenableBuilder(
        listenable: state,
        builder: (context, _) => MaterialApp(
          title: 'Nexis Hub',
          debugShowCheckedModeBanner: false,
          theme: nexisTheme(Brightness.light),
          darkTheme: nexisTheme(Brightness.dark),
          locale: state.locale,
          supportedLocales: AppLocalizations.supportedLocales,
          localizationsDelegates: const [
            AppLocalizations.delegate,
            ...systemDelegates,
          ],
          localeResolutionCallback: (device, supported) {
            for (final locale in supported) {
              if (locale.languageCode == device?.languageCode) return locale;
            }
            return const Locale('fr');
          },
          home: _Root(state: state),
        ),
      ),
    );
  }
}

/// Lancement puis, selon la session, l'accueil ou la bienvenue. Le
/// lancement ne revient pas quand la langue ou la session change.
class _Root extends StatefulWidget {
  const _Root({required this.state});

  final AppState state;

  @override
  State<_Root> createState() => _RootState();
}

class _RootState extends State<_Root> {
  bool _launched = false;

  @override
  Widget build(BuildContext context) {
    if (!_launched) {
      return LaunchScreen(onDone: () => setState(() => _launched = true));
    }
    return widget.state.signedIn ? const Shell() : const WelcomeScreen();
  }
}
