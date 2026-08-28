import 'dart:convert';
import 'dart:io';

/// Tiny best-effort settings store (theme mode + accent). A single JSON file
/// in the platform config dir; every read/write is wrapped so a missing or
/// unwritable location just means "no saved prefs".
class Prefs {
  static File _file() {
    final Map<String, String> env = Platform.environment;
    final String home =
        env['HOME'] ?? env['USERPROFILE'] ?? Directory.systemTemp.path;
    final String base = Platform.isWindows
        ? (env['APPDATA'] ?? '$home\\AppData\\Roaming')
        : Platform.isMacOS
            ? '$home/Library/Application Support'
            : (env['XDG_CONFIG_HOME'] ?? '$home/.config');
    final String sep = Platform.pathSeparator;
    return File('$base${sep}ocforge_gui${sep}prefs.json');
  }

  static Future<Map<String, dynamic>> load() async {
    try {
      final File f = _file();
      if (await f.exists()) {
        return jsonDecode(await f.readAsString()) as Map<String, dynamic>;
      }
    } on Object {
      // no readable prefs
    }
    return <String, dynamic>{};
  }

  static Future<void> save(Map<String, dynamic> data) async {
    try {
      final File f = _file();
      await f.parent.create(recursive: true);
      await f.writeAsString(jsonEncode(data));
    } on Object {
      // nowhere to write — fine, prefs just won't persist
    }
  }
}
