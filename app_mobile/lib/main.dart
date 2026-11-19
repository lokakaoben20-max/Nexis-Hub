import 'package:flutter/material.dart';

import 'app_state.dart';
import 'data/demo_repository.dart';
import 'l10n/app_localizations.dart';
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
          home: state.signedIn ? const Shell() : const WelcomeScreen(),
        ),
      ),
    );
  }
}
