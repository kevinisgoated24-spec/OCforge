import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';

import 'cli.dart';
import 'gui_update.dart';
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

  /// Set by Forge's "Review in Editor" button after a successful build --
  /// the Editor tab picks this up on its next build() (see [consumeTabJump]),
  /// pre-fills its path field, and opens it automatically. Lets a user
  /// hand-check/tweak the just-built config.plist before it's copied to a
  /// USB or EFI partition and actually booted, without retyping the path.
  String? pendingEditorPath;
  int? requestedTabIndex;

  void reviewInEditor(String configPath, {required int editorTabIndex}) {
    pendingEditorPath = configPath;
    requestedTabIndex = editorTabIndex;
    notifyListeners();
  }

  /// Called by the shell once it's acted on [requestedTabIndex], so the same
  /// jump doesn't keep firing on every rebuild.
  void consumeTabJump() {
    requestedTabIndex = null;
  }

  /// Called by the Editor tab once it's picked up [pendingEditorPath].
  void consumeEditorPath() {
    pendingEditorPath = null;
  }

  ThemeMode themeMode = ThemeMode.system;
  AccentTheme accent = AccentTheme.violet;

  /// Anthropic API key for the in-GUI assistant (assistant.dart), used only
  /// when no local Claude Code CLI is found. Stored in the same plaintext
  /// prefs.json as theme/accent -- this app has no OS-keychain integration
  /// (no native plugins at all, by design), so this is a known simplification,
  /// not a securely-stored secret.
  String? aiApiKey;

  bool _prefsLoaded = false;
  bool _disposed = false;

  /// (version, releaseUrl) of a newer GUI release, once the background check
  /// in [init] finds one. Null until then, and stays null if none exists or
  /// the check couldn't complete — never blocks startup either way.
  (String, String)? guiUpdate;

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
      aiApiKey = p['aiApiKey'] is String ? p['aiApiKey'] as String : null;
    }
    cliReady = await cli.resolve();
    notifyListeners();
    unawaited(checkForGuiUpdate().then(((String, String)? r) {
      // The app may have closed before this network call finished --
      // notifyListeners() on a disposed ChangeNotifier throws.
      if (r != null && !_disposed) {
        guiUpdate = r;
        notifyListeners();
      }
    }));
  }

  void _persist() {
    Prefs.save(<String, dynamic>{
      'themeMode': themeMode.name,
      'accent': accent.name,
      if (aiApiKey != null && aiApiKey!.isNotEmpty) 'aiApiKey': aiApiKey,
    });
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

  void setAiApiKey(String? key) {
    aiApiKey = (key == null || key.isEmpty) ? null : key;
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
    _disposed = true;
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
