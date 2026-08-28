import 'dart:convert';
import 'dart:io';

/// One way to reach the `ocforge` Python CLI.
class CliResolution {
  const CliResolution(this.executable, this.prefixArgs, this.label);

  final String executable;
  final List<String> prefixArgs;
  final String label;
}

/// Locates and runs the `ocforge` CLI. If nothing on the machine answers
/// `--version`, [available] stays false and the UI drops into demo mode.
class OcforgeCli {
  static const List<CliResolution> _candidates = <CliResolution>[
    CliResolution('ocforge', <String>[], 'ocforge (on PATH)'),
    CliResolution('py', <String>['-3', '-m', 'ocforge'], 'py -3 -m ocforge'),
    CliResolution('python', <String>['-m', 'ocforge'], 'python -m ocforge'),
    CliResolution('python3', <String>['-m', 'ocforge'], 'python3 -m ocforge'),
  ];

  CliResolution? _resolved;
  String _version = '';

  bool get available => _resolved != null;
  String get label => _resolved?.label ?? 'not found';
  String get version => _version;

  static const Map<String, String> _env = <String, String>{
    'PYTHONUTF8': '1',
    'PYTHONIOENCODING': 'utf-8',
  };

  Future<bool> resolve() async {
    for (final CliResolution c in _candidates) {
      try {
        final ProcessResult r = await Process.run(
          c.executable,
          <String>[...c.prefixArgs, '--version'],
          runInShell: true,
          includeParentEnvironment: true,
          environment: _env,
          stdoutEncoding: utf8,
          stderrEncoding: utf8,
        );
        if (r.exitCode == 0) {
          _resolved = c;
          _version = '${r.stdout}'.trim();
          return true;
        }
      } on ProcessException {
        // try the next candidate
      }
    }
    return false;
  }

  Future<ProcessResult> run(List<String> args) {
    final CliResolution c = _resolved!;
    return Process.run(
      c.executable,
      <String>[...c.prefixArgs, ...args],
      runInShell: true,
      includeParentEnvironment: true,
      environment: _env,
      stdoutEncoding: utf8,
      stderrEncoding: utf8,
    );
  }

  Future<Process> start(List<String> args) {
    final CliResolution c = _resolved!;
    return Process.start(
      c.executable,
      <String>[...c.prefixArgs, ...args],
      runInShell: true,
      includeParentEnvironment: true,
      environment: _env,
    );
  }
}
