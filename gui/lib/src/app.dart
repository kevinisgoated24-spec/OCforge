import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show AppExitResponse;

import 'controller.dart';
import 'pages/build_page.dart';
import 'pages/config_page.dart';
import 'pages/detect_page.dart';
import 'pages/editor_page.dart';
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
  late final AppLifecycleListener _lifecycle;

  // The CLI probe runs inside SetupGate (see below); no need to also kick it
  // off here.

  @override
  void initState() {
    super.initState();
    // On desktop the root State's dispose() isn't guaranteed on window close;
    // this fires reliably, so the Detect temp spec gets cleaned up.
    _lifecycle = AppLifecycleListener(onExitRequested: () async {
      _controller.cleanupTempSpec();
      return AppExitResponse.exit;
    });
  }

  @override
  void dispose() {
    _lifecycle.dispose();
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
          theme: expressiveTheme(Brightness.light, seed: _controller.accent.seed),
          darkTheme: expressiveTheme(Brightness.dark, seed: _controller.accent.seed),
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
    EditorPage(),
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
                  padding: const EdgeInsets.only(bottom: 14),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: <Widget>[
                      PopupMenuButton<AccentTheme>(
                        tooltip: 'Accent colour',
                        icon: const Icon(Icons.palette_outlined),
                        onSelected: c.setAccent,
                        itemBuilder: (BuildContext _) => <PopupMenuEntry<AccentTheme>>[
                          for (final AccentTheme a in AccentTheme.values)
                            PopupMenuItem<AccentTheme>(
                              value: a,
                              child: Row(
                                children: <Widget>[
                                  Container(
                                    width: 14,
                                    height: 14,
                                    decoration: BoxDecoration(
                                        color: a.seed, shape: BoxShape.circle),
                                  ),
                                  const SizedBox(width: 12),
                                  Text(a.label),
                                  if (a == c.accent) ...<Widget>[
                                    const SizedBox(width: 16),
                                    const Icon(Icons.check_rounded, size: 16),
                                  ],
                                ],
                              ),
                            ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      IconButton(
                        tooltip: 'Theme: ${c.themeMode.name}',
                        onPressed: c.cycleTheme,
                        icon: Icon(switch (c.themeMode) {
                          ThemeMode.light => Icons.light_mode_outlined,
                          ThemeMode.dark => Icons.dark_mode_outlined,
                          ThemeMode.system => Icons.brightness_auto_outlined,
                        }),
                      ),
                    ],
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
              NavigationRailDestination(
                icon: Icon(Icons.edit_note_rounded),
                label: Text('Editor'),
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
