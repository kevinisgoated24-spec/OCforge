import 'dart:convert';
import 'dart:io';

/// The GUI's own version — kept in sync by hand with pubspec.yaml's
/// `version:` and [OcforgeCli.minVersion] (cli.dart), same manual-bump
/// convention already used for every gui-v* tag.
const String appVersion = '0.4.28';

const String _latestReleaseApi =
    'https://api.github.com/repos/kevinisgoated24-spec/OCforge/releases/latest';

/// Checks GitHub for a newer `gui-v*` release than [appVersion]. Returns
/// `(version, releaseUrl)` if one exists, or null if already current or the
/// check couldn't complete (offline, rate-limited, malformed response, …) —
/// this never throws into the caller and should never block startup on it.
Future<(String, String)?> checkForGuiUpdate() async {
  HttpClient? client;
  try {
    client = HttpClient()..connectionTimeout = const Duration(seconds: 6);
    final HttpClientRequest req = await client.getUrl(Uri.parse(_latestReleaseApi));
    req.headers.set(HttpHeaders.userAgentHeader, 'ocforge-gui');
    req.headers.set(HttpHeaders.acceptHeader, 'application/vnd.github+json');
    final HttpClientResponse resp = await req.close();
    if (resp.statusCode != 200) return null;
    final String body = await resp.transform(utf8.decoder).join();
    final Map<String, dynamic> json = jsonDecode(body) as Map<String, dynamic>;
    final String tag = (json['tag_name'] as String?) ?? '';
    final String latest = tag.startsWith('gui-v') ? tag.substring(5) : tag;
    if (latest.isEmpty || !_isNewer(latest, appVersion)) return null;
    final String url = (json['html_url'] as String?) ??
        'https://github.com/kevinisgoated24-spec/OCforge/releases/tag/$tag';
    return (latest, url);
  } on Object {
    return null;
  } finally {
    client?.close(force: true);
  }
}

List<int> _parseVersion(String s) {
  final Match? m = RegExp(r'(\d+)\.(\d+)\.(\d+)').firstMatch(s);
  if (m == null) return <int>[0, 0, 0];
  return <int>[int.parse(m[1]!), int.parse(m[2]!), int.parse(m[3]!)];
}

bool _isNewer(String candidate, String current) {
  final List<int> a = _parseVersion(candidate);
  final List<int> b = _parseVersion(current);
  for (int i = 0; i < 3; i++) {
    if (a[i] != b[i]) return a[i] > b[i];
  }
  return false;
}

/// Opens [url] in the platform's default browser, best-effort.
Future<void> openInBrowser(String url) async {
  try {
    if (Platform.isWindows) {
      await Process.run('explorer', <String>[url], runInShell: true);
    } else if (Platform.isMacOS) {
      await Process.run('open', <String>[url]);
    } else {
      await Process.run('xdg-open', <String>[url]);
    }
  } on ProcessException {
    // best effort — worst case the user copies the URL from the terminal
  }
}
