import 'package:flutter/material.dart';

import 'cli.dart';

/// App-wide state: the resolved CLI, the current spec, the last plan text and
/// the shared macOS-target override. Plain [ChangeNotifier] so there are no
/// package dependencies to resolve in CI.
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

  Future<void> init() async {
    cliReady = await cli.resolve();
    notifyListeners();
  }

  void cycleTheme() {
    themeMode = ThemeMode.values[(themeMode.index + 1) % ThemeMode.values.length];
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
