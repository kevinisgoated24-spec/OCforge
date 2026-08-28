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

  void setSpec(String path, String label, Map<String, dynamic>? m) {
    specPath = path;
    specLabel = label;
    machine = m;
    notifyListeners();
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
