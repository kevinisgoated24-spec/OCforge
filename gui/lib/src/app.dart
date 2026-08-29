import 'dart:io';

import 'package:flutter/material.dart';

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

class _OcforgeAppState extends State<OcforgeApp> with WidgetsBindingObserver {
  final OcforgeController _controller = OcforgeController();

  // The CLI probe runs inside SetupGate (see below); no need to also kick it
  // off here.

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // On desktop the root State's dispose() isn't guaranteed on window close;
    // 'detached' fires as the app tears down, so clean up the Detect temp spec.
    if (state == AppLifecycleState.detached) _controller.cleanupTempSpec();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
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
                      const SizedBox(height: 4),
                      IconButton(
                        tooltip: 'Report a bug (OCforgeReporter)',
                        onPressed: () => _reportBug(c),
                        icon: const Icon(Icons.bug_report_outlined),
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
                if (c.guiUpdate != null)
                  GuiUpdateBanner(version: c.guiUpdate!.$1, url: c.guiUpdate!.$2),
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

/// OCforgeReporter: no bot, no server, no shared credentials — this just
/// pre-fills the repo's bug-report issue form and opens it in the browser.
/// The user reviews it and submits under their own GitHub account, same as
/// `ocforge report` on the CLI.
Future<void> _reportBug(OcforgeController c) async {
  final String hardware = c.machine != null
      ? _formatMachineForReport(c.machine!)
      : "(run Detect first, or paste your spec.json / `ocforge probe` output here)";
  final Uri uri = Uri.https(
    'github.com',
    '/kevinisgoated24-spec/OCforge/issues/new',
    <String, String>{
      'template': 'bug_report.yml',
      'title': '[Bug]: ',
      'labels': 'bug',
      'ocforge-version': c.cli.version.isEmpty ? 'unknown (CLI not detected)' : c.cli.version,
      'os': Platform.isWindows ? 'Windows' : (Platform.isMacOS ? 'macOS' : 'Linux'),
      'interface': 'GUI',
      'hardware': hardware,
    },
  );
  try {
    if (Platform.isWindows) {
      await Process.run('explorer', <String>[uri.toString()], runInShell: true);
    } else if (Platform.isMacOS) {
      await Process.run('open', <String>[uri.toString()]);
    } else {
      await Process.run('xdg-open', <String>[uri.toString()]);
    }
  } on ProcessException {
    // best effort — worst case the user copies the URL from the terminal
  }
}

String _formatMachineForReport(Map<String, dynamic> m) {
  final StringBuffer b = StringBuffer();
  b.writeln('chassis   ${m['chassis'] ?? '?'}');

  final Map<String, dynamic> cpu = (m['cpu'] as Map?)?.cast<String, dynamic>() ?? <String, dynamic>{};
  final String fam = (cpu['family'] as String?) ?? '';
  final int gen = (cpu['intel_gen'] as num?)?.toInt() ?? 0;
  b.writeln('cpu       ${cpu['brand'] ?? '?'}  '
      '[${cpu['vendor'] ?? '?'}${fam.isNotEmpty ? ' / $fam' : ''}'
      '${gen > 0 ? ' (Intel gen $gen)' : ''}]  '
      '${cpu['cores'] ?? '?'}c/${cpu['threads'] ?? '?'}t');

  for (final String key in <String>['igpu', 'dgpu']) {
    final Map<String, dynamic>? g = (m[key] as Map?)?.cast<String, dynamic>();
    if (g == null) continue;
    final Map<String, dynamic>? pci = (g['pci'] as Map?)?.cast<String, dynamic>();
    final String pciStr = pci != null && (pci['vendor'] ?? '').toString().isNotEmpty
        ? '  [${pci['vendor']}:${pci['device']}]'
        : '';
    b.writeln('gpu       ${key == 'igpu' ? 'iGPU' : 'dGPU'}: ${g['name']} (${g['vendor']})$pciStr');
  }

  for (final dynamic raw in (m['net'] as List?) ?? const <dynamic>[]) {
    final Map<String, dynamic> n = (raw as Map).cast<String, dynamic>();
    final bool wireless = n['wireless'] == true;
    b.writeln('${wireless ? 'wifi' : 'eth '}      ${n['name'] ?? '?'} (${n['vendor'] ?? '?'})');
  }

  final Map<String, dynamic> storage = (m['storage'] as Map?)?.cast<String, dynamic>() ?? <String, dynamic>{};
  b.writeln('storage   nvme=${storage['has_nvme'] == true ? 'yes' : 'no'}');

  final Map<String, dynamic> fw = (m['firmware'] as Map?)?.cast<String, dynamic>() ?? <String, dynamic>{};
  if ((fw['board_name'] ?? '').toString().isNotEmpty) {
    b.writeln('board     ${fw['board_vendor'] ?? ''} ${fw['board_name'] ?? ''}'.trim());
  }

  return b.toString().trim();
}
