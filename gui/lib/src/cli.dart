import 'dart:convert';
import 'dart:io';

/// One way to reach the `ocforge` Python CLI.
class CliResolution {
  const CliResolution(this.executable, this.prefixArgs, this.label);

  final String executable;
  final List<String> prefixArgs;
  final String label;
}

/// A working Python interpreter on this machine.
class PythonInfo {
  const PythonInfo(this.executable, this.baseArgs, this.version);

  final String executable; // 'py' | 'python' | 'python3'
  final List<String> baseArgs; // ['-3'] for the py launcher
  final String version; // e.g. "Python 3.12.8"

  List<String> cmd(List<String> rest) => <String>[...baseArgs, ...rest];
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

  /// The oldest `ocforge` this GUI build is happy to drive. Bump alongside the
  /// gui-v* tag when a CLI fix needs to reach users.
  static const String minVersion = '0.4.19';

  CliResolution? _resolved;
  String _version = '';

  bool get available => _resolved != null;
  String get label => _resolved?.label ?? 'not found';
  String get version => _version;

  static List<int> _parseVersion(String s) {
    final Match? m = RegExp(r'(\d+)\.(\d+)\.(\d+)').firstMatch(s);
    if (m == null) return <int>[0, 0, 0];
    return <int>[int.parse(m[1]!), int.parse(m[2]!), int.parse(m[3]!)];
  }

  /// True when a resolved CLI is older than [minVersion] (or unparseable).
  bool get outdated {
    if (_resolved == null) return false; // "missing" is a different state
    final List<int> got = _parseVersion(_version);
    final List<int> need = _parseVersion(minVersion);
    for (int i = 0; i < 3; i++) {
      if (got[i] != need[i]) return got[i] < need[i];
    }
    return false;
  }

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

  // --- first-run bootstrap ------------------------------------------------

  static const String zipballUrl =
      'https://github.com/kevinisgoated24-spec/OCforge/archive/refs/heads/master.zip';

  /// The first Python that answers `--version`, or null if none is installed.
  static Future<PythonInfo?> findPython() async {
    const List<List<String>> probes = <List<String>>[
      <String>['py', '-3'],
      <String>['python3'],
      <String>['python'],
    ];
    for (final List<String> p in probes) {
      try {
        final ProcessResult r = await Process.run(
          p.first,
          <String>[...p.skip(1), '--version'],
          runInShell: true,
          stdoutEncoding: utf8,
          stderrEncoding: utf8,
        );
        final String v = ('${r.stdout}${r.stderr}').trim();
        // The Microsoft Store stub exits non-zero and prints an install hint.
        if (r.exitCode == 0 && v.toLowerCase().startsWith('python')) {
          return PythonInfo(p.first, p.skip(1).toList(), v);
        }
      } on ProcessException {
        // next probe
      }
    }
    return null;
  }

  /// `pip install --user` the ocforge zipball with the given interpreter.
  /// Streams output through [log]; returns the process exit code.
  static Future<int> installOcforge(PythonInfo py, void Function(String) log) async {
    Future<(int, bool)> pip(List<String> extraArgs) async {
      final List<String> args = py.cmd(<String>[
        '-m', 'pip', 'install', '--user', '--upgrade', '--disable-pip-version-check',
        ...extraArgs,
        zipballUrl,
      ]);
      log('\$ ${py.executable} ${args.join(' ')}');
      final Process proc = await Process.start(py.executable, args,
          runInShell: true, environment: _env, includeParentEnvironment: true);
      const Utf8Decoder dec = Utf8Decoder(allowMalformed: true);
      bool externallyManaged = false;
      void handle(String line) {
        if (line.contains('externally-managed-environment')) externallyManaged = true;
        log(line);
      }
      final Future<void> outDone =
          proc.stdout.transform(dec).transform(const LineSplitter()).forEach(handle);
      final Future<void> errDone =
          proc.stderr.transform(dec).transform(const LineSplitter()).forEach(handle);
      final int code = await proc.exitCode;
      // exitCode can resolve before the piped streams finish draining —
      // wait for both so `externallyManaged` is settled before we read it.
      await Future.wait(<Future<void>>[outDone, errDone]);
      return (code, externallyManaged);
    }

    var (int code, bool managed) = await pip(const <String>[]);
    if (managed) {
      // Debian/Ubuntu and other PEP 668 distros: the system pip refuses
      // `--user` installs outside a venv unless told this is deliberate.
      log('System Python is externally managed — retrying with --break-system-packages …');
      (code, managed) = await pip(const <String>['--break-system-packages']);
    }
    if (code != 0 && !managed) {
      // Old/edge Pythons without pip wired up.
      log('pip unavailable — bootstrapping it with ensurepip …');
      final ProcessResult ep = await Process.run(
        py.executable,
        py.cmd(<String>['-m', 'ensurepip', '--default-pip']),
        runInShell: true,
      );
      log('${ep.stdout}${ep.stderr}'.trim());
      if (ep.exitCode == 0) {
        (code, managed) = await pip(const <String>[]);
        if (managed) {
          (code, managed) = await pip(const <String>['--break-system-packages']);
        }
      }
    }
    return code;
  }

  /// Best-effort Python install via winget. Returns exit code, or -1 when
  /// winget itself isn't available.
  static Future<int> wingetInstallPython(void Function(String) log) async {
    const List<String> args = <String>[
      'install', '-e', '--id', 'Python.Python.3.12', '--source', 'winget',
      '--accept-package-agreements', '--accept-source-agreements',
    ];
    log('\$ winget ${args.join(' ')}');
    try {
      final Process proc =
          await Process.start('winget', args, runInShell: true);
      const Utf8Decoder dec = Utf8Decoder(allowMalformed: true);
      proc.stdout.transform(dec).transform(const LineSplitter()).listen(log);
      proc.stderr.transform(dec).transform(const LineSplitter()).listen(log);
      return await proc.exitCode;
    } on ProcessException {
      log('winget not found on this system');
      return -1;
    }
  }
}
