import 'package:flutter/material.dart';

import '../app_state.dart';

/// Charge des données du dépôt et affiche l'écran quand elles sont là.
class Loaded<T> extends StatefulWidget {
  const Loaded({super.key, required this.load, required this.builder});

  final Future<T> Function() load;
  final Widget Function(BuildContext context, T data) builder;

  @override
  State<Loaded<T>> createState() => _LoadedState<T>();
}

class _LoadedState<T> extends State<Loaded<T>> {
  late Future<T> _future;
  int? _revision;
  T? _last;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final revision = AppScope.of(context).revision;
    if (revision != _revision) {
      _revision = revision;
      _future = widget.load().then((value) => _last = value);
    }
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<T>(
    future: _future,
    builder: (context, snapshot) {
      if (snapshot.hasData) return widget.builder(context, snapshot.data as T);
      // Pendant un rechargement, on garde l'écran précédent.
      if (_last != null && snapshot.connectionState != ConnectionState.done) {
        return widget.builder(context, _last as T);
      }
      if (snapshot.hasError) return Center(child: Text('${snapshot.error}'));
      return const Center(child: CircularProgressIndicator());
    },
  );
}
