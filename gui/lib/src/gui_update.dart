import 'dart:convert';
import 'dart:io';

/// The GUI's own version — kept in sync by hand with pubspec.yaml's
/// `version:` and [OcforgeCli.minVersion] (cli.dart), same manual-bump
/// convention already used for every gui-v* tag.
const String appVersion = '1.0.0';

/// Each stable (non-beta) major/notable release gets a codename, changed by
/// hand alongside [appVersion] -- purely cosmetic, shown in the splash
/// credits and the update banner.
const String appCodename = 'Bromine';

const String _releasesListApi =
    'https://api.github.com/repos/kevinisgoated24-spec/OCforge/releases?per_page=20';

/// Checks GitHub for a newer release than [appVersion]. Returns
/// `(version, releaseUrl, isBeta)` if one exists, or null if already current
/// or the check couldn't complete (offline, rate-limited, malformed
/// response, …) — this never throws into the caller and should never block
/// startup on it.
///
/// Lists releases and picks the newest by version number itself, rather
/// than GitHub's own `/releases/latest` — that endpoint only ever returns
/// the newest *non-prerelease*, and every release here is tagged
/// pre-release while this project isn't public yet (draft releases are
/// never included here regardless: GitHub only returns those to an
/// authenticated request, and this one carries no token).
///
/// Two tag families exist: `gui-v*` (stable — always considered) and
/// `gui-beta-v*` (beta — only considered when [includeBeta] is true, i.e.
/// the user opted into the beta channel via [OcforgeController.betaChannel]).
/// Whichever family has the numerically newer version wins; [isBeta] on the
/// result says which one was picked, so the caller (the update banner/dialog)
/// can label it and fetch the right tag.
Future<(String, String, bool)?> checkForGuiUpdate({bool includeBeta = false}) async {
  HttpClient? client;
  try {
    client = HttpClient()..connectionTimeout = const Duration(seconds: 6);
    final HttpClientRequest req = await client.getUrl(Uri.parse(_releasesListApi));
    req.headers.set(HttpHeaders.userAgentHeader, 'ocforge-gui');
    req.headers.set(HttpHeaders.acceptHeader, 'application/vnd.github+json');
    final HttpClientResponse resp = await req.close();
    if (resp.statusCode != 200) return null;
    final String body = await resp.transform(utf8.decoder).join();
    final List<dynamic> releases = jsonDecode(body) as List<dynamic>;

    String? bestVersion;
    String? bestUrl;
    bool bestIsBeta = false;
    for (final dynamic r in releases) {
      final Map<String, dynamic> rel = r as Map<String, dynamic>;
      final String tag = (rel['tag_name'] as String?) ?? '';
      final bool isBetaTag = tag.startsWith('gui-beta-v');
      final String prefix = isBetaTag ? 'gui-beta-v' : 'gui-v';
      if (!tag.startsWith(prefix)) continue;
      if (isBetaTag && !includeBeta) continue;
      final String version = tag.substring(prefix.length);
      if (bestVersion == null || _isNewer(version, bestVersion)) {
        bestVersion = version;
        bestIsBeta = isBetaTag;
        bestUrl = (rel['html_url'] as String?) ??
            'https://github.com/kevinisgoated24-spec/OCforge/releases/tag/$tag';
      }
    }
    if (bestVersion == null || !_isNewer(bestVersion, appVersion)) return null;
    return (bestVersion, bestUrl!, bestIsBeta);
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
      // No runInShell: a URL routed through cmd.exe has its unescaped &s
      // (query-string separators) treated as command separators, mangling
      // the argument explorer actually receives. See app.dart's _reportBug
      // for the concrete case this broke.
      await Process.run('explorer', <String>[url]);
    } else if (Platform.isMacOS) {
      await Process.run('open', <String>[url]);
    } else {
      await Process.run('xdg-open', <String>[url]);
    }
  } on ProcessException {
    // best effort — worst case the user copies the URL from the terminal
  }
}
