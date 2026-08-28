import 'package:flutter/material.dart';

import 'controller.dart';
import 'pages/build_page.dart';
import 'pages/config_page.dart';
import 'pages/detect_page.dart';
import 'pages/plan_page.dart';
import 'setup.dart';
import 'theme.dart';
import 'widgets.dart';

class OcforgeApp extends StatefulWidget {
  const OcforgeApp({super.key});

  @override
  State<OcforgeApp> createState() => _OcforgeAppState();
}

class _OcforgeAppState extends State<OcforgeApp> {
  final OcforgeController _controller = OcforgeController();

  // The CLI probe runs inside SetupGate (see below); no need to also kick it
  // off here.

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ControllerScope(
      controller: _controller,
      child: AnimatedBuilder(
        animation: _controller,
        builder: (BuildContext context, _) => MaterialApp(
          title: 'OCForge',
          debugShowCheckedModeBanner: false,
          theme: expressiveTheme(Brightness.light),
          darkTheme: expressiveTheme(Brightness.dark),
          themeMode: _controller.themeMode,
          home: const SetupGate(child: _Shell()),
        ),
      ),
    );
  }
}

class _Shell extends StatefulWidget {
  const _Shell();

  @override
  State<_Shell> createState() => _ShellState();
}

class _ShellState extends State<_Shell> {
  int _index = 0;

  static const List<Widget> _pages = <Widget>[
    DetectPage(),
    PlanPage(),
    ConfigPage(),
    BuildPage(),
  ];

  @override
  Widget build(BuildContext context) {
    final OcforgeController c = ControllerScope.of(context);

    return Scaffold(
      body: Row(
        children: <Widget>[
          NavigationRail(
            selectedIndex: _index,
            onDestinationSelected: (int i) => setState(() => _index = i),
            groupAlignment: -0.7,
            leading: const Padding(
              padding: EdgeInsets.symmetric(vertical: 14),
              child: AppGlyph(),
            ),
            trailing: Expanded(
              child: Align(
                alignment: Alignment.bottomCenter,
                child: Padding(
                  padding: const EdgeInsets.only(bottom: 16),
                  child: IconButton(
                    tooltip: 'Theme: ${c.themeMode.name}',
                    onPressed: c.cycleTheme,
                    icon: Icon(switch (c.themeMode) {
                      ThemeMode.light => Icons.light_mode_outlined,
                      ThemeMode.dark => Icons.dark_mode_outlined,
                      ThemeMode.system => Icons.brightness_auto_outlined,
                    }),
                  ),
                ),
              ),
            ),
            destinations: const <NavigationRailDestination>[
              NavigationRailDestination(
                icon: Icon(Icons.search_rounded),
                label: Text('Detect'),
              ),
              NavigationRailDestination(
                icon: Icon(Icons.tune_rounded),
                label: Text('Plan'),
              ),
              NavigationRailDestination(
                icon: Icon(Icons.rule_rounded),
                label: Text('Config'),
              ),
              NavigationRailDestination(
                icon: Icon(Icons.hardware_rounded),
                label: Text('Forge'),
              ),
            ],
          ),
          const VerticalDivider(width: 1),
          Expanded(
            child: Column(
              children: <Widget>[
                if (c.demo) const DemoBanner(),
                Expanded(
                  child: AnimatedSwitcher(
                    duration: const Duration(milliseconds: 340),
                    switchInCurve: Curves.easeOutCubic,
                    switchOutCurve: Curves.easeIn,
                    transitionBuilder: (Widget child, Animation<double> a) =>
                        FadeTransition(
                      opacity: a,
                      child: SlideTransition(
                        position: Tween<Offset>(
                          begin: const Offset(0, 0.03),
                          end: Offset.zero,
                        ).animate(a),
                        child: child,
                      ),
                    ),
                    child: KeyedSubtree(
                      key: ValueKey<int>(_index),
                      child: _pages[_index],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
