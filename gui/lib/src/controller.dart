import 'dart:io';

import 'package:flutter/material.dart';

import 'cli.dart';
import 'prefs.dart';
import 'theme.dart';

/// App-wide state: the resolved CLI, the current spec, the last plan text, the
/// shared macOS-target override and the look (theme mode + accent, persisted).
/// Plain [ChangeNotifier] so there are no package dependencies to resolve in CI.
class OcforgeController extends ChangeNotifier {
  final OcforgeCli cli = OcforgeCli();

  bool cliReady = false;
  bool get demo => !cliReady;

  String? specPath;
  String? specLabel;
  Map<String, dynamic>? machine;
  String? planText;
  bool _specIsTemp = false; // true when the GUI wrote specPath itself (Detect)

  /// null == "Auto (recommended)".
  int? macosOverride;

  ThemeMode themeMode = ThemeMode.system;
  AccentTheme accent = AccentTheme.violet;

  bool _prefsLoaded = false;

  Future<void> init() async {
    if (!_prefsLoaded) {
      _prefsLoaded = true;
      final Map<String, dynamic> p = await Prefs.load();
      final Object? mode = p['themeMode'];
      themeMode = ThemeMode.values.firstWhere(
        (ThemeMode m) => m.name == mode,
        orElse: () => ThemeMode.system,
      );
      accent = AccentTheme.byName(p['accent'] is String ? p['accent'] as String : null);
    }
    cliReady = await cli.resolve();
    notifyListeners();
  }

  void _persist() {
    Prefs.save(<String, dynamic>{'themeMode': themeMode.name, 'accent': accent.name});
  }

  void cycleTheme() {
    themeMode = ThemeMode.values[(themeMode.index + 1) % ThemeMode.values.length];
    _persist();
    notifyListeners();
  }

  void setAccent(AccentTheme a) {
    accent = a;
    _persist();
    notifyListeners();
  }

  /// [temp] marks a spec file the GUI created itself (via Detect) — it is
  /// deleted when replaced by another spec and when the app shuts down. A spec
  /// the user opened from disk is never touched.
  void setSpec(String path, String label, Map<String, dynamic>? m, {bool temp = false}) {
    cleanupTempSpec(); // clean up the previous Detect spec, if any
    specPath = path;
    specLabel = label;
    machine = m;
    _specIsTemp = temp;
    notifyListeners();
  }

  /// Delete the GUI-created Detect spec file, if one is current. Idempotent;
  /// safe to call on app exit and again from [dispose].
  void cleanupTempSpec() {
    if (!_specIsTemp || specPath == null) return;
    try {
      final File f = File(specPath!);
      if (f.existsSync()) f.deleteSync();
    } on Object {
      // best effort — a leftover temp file is harmless
    }
    _specIsTemp = false;
  }

  @override
  void dispose() {
    cleanupTempSpec();
    super.dispose();
  }

  void setPlan(String text) {
    planText = text;
    notifyListeners();
  }

  void setMacos(int? major) {
    macosOverride = major;
    notifyListeners();
  }
}

class ControllerScope extends InheritedNotifier<OcforgeController> {
  const ControllerScope({
    super.key,
    required OcforgeController controller,
    required super.child,
  }) : super(notifier: controller);

  static OcforgeController of(BuildContext context) {
    final ControllerScope? scope =
        context.dependOnInheritedWidgetOfExactType<ControllerScope>();
    assert(scope != null, 'No ControllerScope in the widget tree');
    return scope!.notifier!;
  }
}
