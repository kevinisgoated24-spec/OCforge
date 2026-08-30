import 'package:flutter/material.dart';

import 'widgets.dart';

/// A brief credits splash shown over [child] on every launch — fades out on
/// its own after ~2 seconds, no interaction needed. Purely cosmetic: it
/// doesn't gate anything, [child] (the real app, including its own
/// first-run setup check) is already mounted and running underneath the
/// whole time, so nothing is delayed by it.
class SplashGate extends StatefulWidget {
  const SplashGate({super.key, required this.child});

  final Widget child;

  @override
  State<SplashGate> createState() => _SplashGateState();
}

class _SplashGateState extends State<SplashGate> {
  bool _visible = true;

  @override
  void initState() {
    super.initState();
    Future<void>.delayed(const Duration(seconds: 2), () {
      if (mounted) setState(() => _visible = false);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: <Widget>[
        widget.child,
        // ignoring: once faded out, clicks must pass straight through to
        // the real app underneath rather than hitting an invisible overlay.
        IgnorePointer(
          ignoring: !_visible,
          child: AnimatedOpacity(
            opacity: _visible ? 1 : 0,
            duration: const Duration(milliseconds: 500),
            curve: Curves.easeOut,
            child: const _SplashScreen(),
          ),
        ),
      ],
    );
  }
}

class _SplashScreen extends StatelessWidget {
  const _SplashScreen();

  @override
  Widget build(BuildContext context) {
    final ColorScheme s = Theme.of(context).colorScheme;
    return Material(
      color: s.surface,
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            const AppGlyph(size: 64),
            const SizedBox(height: 20),
            Text('OCForge', style: Theme.of(context).textTheme.headlineMedium),
            const SizedBox(height: 28),
            Text('Made by: KevinMayBeHere',
                style: TextStyle(color: s.onSurfaceVariant, fontSize: 13)),
            const SizedBox(height: 4),
            Text('Tested by: GaM1ng',
                style: TextStyle(color: s.onSurfaceVariant, fontSize: 13)),
          ],
        ),
      ),
    );
  }
}
