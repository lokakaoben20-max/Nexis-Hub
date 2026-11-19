import 'package:flutter/material.dart';

/// Charge des données du dépôt et affiche l'écran quand elles sont là.
class Loaded<T> extends StatefulWidget {
  const Loaded({super.key, required this.load, required this.builder});

  final Future<T> Function() load;
  final Widget Function(BuildContext context, T data) builder;

  @override
  State<Loaded<T>> createState() => _LoadedState<T>();
}

class _LoadedState<T> extends State<Loaded<T>> {
  late final Future<T> _future = widget.load();

  @override
  Widget build(BuildContext context) => FutureBuilder<T>(
    future: _future,
    builder: (context, snapshot) {
      if (snapshot.hasData) return widget.builder(context, snapshot.data as T);
      if (snapshot.hasError) return Center(child: Text('${snapshot.error}'));
      return const Center(child: CircularProgressIndicator());
    },
  );
}
