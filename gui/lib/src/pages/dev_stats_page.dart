import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';

import '../widgets.dart';

/// Repo-wide download/activity numbers, read straight from GitHub's public
/// REST API -- no token, no backend of ocforge's own. Every number here is
/// already publicly visible on the repo/releases pages; this just puts it
/// in one place instead of clicking through each release.
class DevStatsPage extends StatefulWidget {
  const DevStatsPage({super.key});

  @override
  State<DevStatsPage> createState() => _DevStatsPageState();
}

class _ReleaseStat {
  _ReleaseStat(this.tag, this.downloads, this.total);
  final String tag;
  final Map<String, int> downloads; // asset name -> count
  final int total;
}

class _DevStatsPageState extends State<DevStatsPage> {
  bool _loading = true;
  String? _error;
  int _stars = 0;
  int _forks = 0;
  int _watchers = 0;
  int _openIssues = 0;
  List<_ReleaseStat> _releases = <_ReleaseStat>[];

  static const String _repo = 'kevinisgoated24-spec/OCforge';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<Map<String, dynamic>?> _getJson(String path) async {
    final HttpClient client = HttpClient()..connectionTimeout = const Duration(seconds: 8);
    try {
      final HttpClientRequest req =
          await client.getUrl(Uri.parse('https://api.github.com/repos/$_repo$path'));
      req.headers.set(HttpHeaders.userAgentHeader, 'ocforge-gui');
      req.headers.set(HttpHeaders.acceptHeader, 'application/vnd.github+json');
      final HttpClientResponse resp = await req.close();
      final String body = await resp.transform(utf8.decoder).join();
      if (resp.statusCode != 200) return null;
      return <String, dynamic>{'body': body};
    } on Object {
      return null;
    } finally {
      client.close(force: true);
    }
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final Map<String, dynamic>? repoRes = await _getJson('');
      if (repoRes == null) throw Exception('could not reach the GitHub API');
      final Map<String, dynamic> repo = jsonDecode(repoRes['body'] as String) as Map<String, dynamic>;

      final Map<String, dynamic>? relRes = await _getJson('/releases?per_page=100');
      final List<dynamic> releases =
          relRes == null ? <dynamic>[] : jsonDecode(relRes['body'] as String) as List<dynamic>;

      final List<_ReleaseStat> stats = <_ReleaseStat>[];
      for (final dynamic r in releases) {
        final Map<String, dynamic> rel = r as Map<String, dynamic>;
        final Map<String, int> perAsset = <String, int>{};
        int total = 0;
        for (final dynamic a in (rel['assets'] as List<dynamic>? ?? <dynamic>[])) {
          final Map<String, dynamic> asset = a as Map<String, dynamic>;
          final int count = (asset['download_count'] as num?)?.toInt() ?? 0;
          perAsset[(asset['name'] as String?) ?? '?'] = count;
          total += count;
        }
        stats.add(_ReleaseStat((rel['tag_name'] as String?) ?? '?', perAsset, total));
      }

      if (!mounted) return;
      setState(() {
        _stars = (repo['stargazers_count'] as num?)?.toInt() ?? 0;
        _forks = (repo['forks_count'] as num?)?.toInt() ?? 0;
        _watchers = (repo['subscribers_count'] as num?)?.toInt() ?? 0;
        _openIssues = (repo['open_issues_count'] as num?)?.toInt() ?? 0;
        _releases = stats;
        _loading = false;
      });
    } on Object catch (e) {
      if (!mounted) return;
      setState(() {
        _error = '$e';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final ColorScheme s = Theme.of(context).colorScheme;
    final int totalDownloads = _releases.fold(0, (int sum, _ReleaseStat r) => sum + r.total);

    return Padding(
      padding: const EdgeInsets.fromLTRB(28, 28, 28, 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Text('Dev stats', style: Theme.of(context).textTheme.headlineMedium),
              const Spacer(),
              IconButton(
                tooltip: 'Refresh',
                onPressed: _loading ? null : _load,
                icon: const Icon(Icons.refresh_rounded),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            'Public GitHub numbers for the repo — nothing here comes from a server of '
            "ocforge's own.",
            style: TextStyle(color: s.onSurfaceVariant, fontSize: 12.5),
          ),
          const SizedBox(height: 20),
          if (_loading)
            const Expanded(child: Center(child: CircularProgressIndicator()))
          else if (_error != null)
            Expanded(
              child: Center(
                child: Text('Could not load stats: $_error',
                    style: TextStyle(color: s.error)),
              ),
            )
          else
            Expanded(
              child: SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Wrap(
                      spacing: 12,
                      runSpacing: 12,
                      children: <Widget>[
                        _StatTile(label: 'Total downloads', value: '$totalDownloads', s: s),
                        _StatTile(label: 'Stars', value: '$_stars', s: s),
                        _StatTile(label: 'Forks', value: '$_forks', s: s),
                        _StatTile(label: 'Watchers', value: '$_watchers', s: s),
                        _StatTile(label: 'Open issues', value: '$_openIssues', s: s),
                      ],
                    ),
                    const SizedBox(height: 28),
                    Text('Downloads by release',
                        style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 12),
                    for (final _ReleaseStat r in _releases)
                      ExpressiveCard(
                        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            Row(
                              children: <Widget>[
                                Text(r.tag, style: const TextStyle(fontWeight: FontWeight.w700)),
                                const Spacer(),
                                Text('${r.total} total',
                                    style: TextStyle(color: s.onSurfaceVariant, fontSize: 12.5)),
                              ],
                            ),
                            for (final MapEntry<String, int> e in r.downloads.entries)
                              Padding(
                                padding: const EdgeInsets.only(top: 6),
                                child: Row(
                                  children: <Widget>[
                                    Expanded(
                                      child: Text(e.key,
                                          style: TextStyle(
                                              color: s.onSurfaceVariant, fontSize: 12.5)),
                                    ),
                                    Text('${e.value}',
                                        style: const TextStyle(
                                            fontWeight: FontWeight.w600, fontSize: 12.5)),
                                  ],
                                ),
                              ),
                          ],
                        ),
                      ),
                    const SizedBox(height: 8),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _StatTile extends StatelessWidget {
  const _StatTile({required this.label, required this.value, required this.s});

  final String label;
  final String value;
  final ColorScheme s;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 140,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      decoration: BoxDecoration(
        color: s.secondaryContainer,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(value,
              style: TextStyle(
                  color: s.onSecondaryContainer, fontSize: 22, fontWeight: FontWeight.w700)),
          const SizedBox(height: 2),
          Text(label, style: TextStyle(color: s.onSecondaryContainer, fontSize: 12)),
        ],
      ),
    );
  }
}
