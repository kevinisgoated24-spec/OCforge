import 'dart:async';
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
  static List<CliResolution> get _candidates => <CliResolution>[
        const CliResolution('ocforge', <String>[], 'ocforge (on PATH)'),
        if (Platform.isWindows)
          const CliResolution('py', <String>['-3', '-m', 'ocforge'], 'py -3 -m ocforge'),
        // Versioned names first off Windows: on macOS a bare `python3` is
        // usually Apple's /usr/bin/python3 (3.9, too old for ocforge), while
        // Homebrew/python.org install `python3.12` & co. alongside it.
        if (!Platform.isWindows)
          for (final String v in _pythonVersions)
            CliResolution('python$v', <String>['-m', 'ocforge'], 'python$v -m ocforge'),
        const CliResolution('python', <String>['-m', 'ocforge'], 'python -m ocforge'),
        const CliResolution('python3', <String>['-m', 'ocforge'], 'python3 -m ocforge'),
      ];

  /// Newest first. ocforge needs 3.11+ (pyproject `requires-python`).
  static const List<String> _pythonVersions = <String>['3.14', '3.13', '3.12', '3.11'];

  /// The oldest `ocforge` this GUI build is happy to drive. Bump alongside the
  /// gui-v* tag when a CLI fix needs to reach users.
  static const String minVersion = '1.3.0';

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

  static Map<String, String> get _env => processEnv;

  /// Environment for every child process the GUI starts (ocforge, Python,
  /// pip/pipx, claude). Rebuilt on each call so a `~/Library/Python/3.x/bin`
  /// created by an install moments ago is picked up without a restart.
  ///
  /// The PATH part matters on macOS: an app opened from Finder/the Dock gets
  /// launchd's bare `/usr/bin:/bin:/usr/sbin:/sbin`, not the shell's PATH, so
  /// Homebrew, python.org Python, `pip install --user` scripts and pipx are
  /// all invisible. Those dirs are *appended*, so a PATH the user did pass
  /// (launched from a terminal) still wins.
  static Map<String, String> get processEnv {
    final Map<String, String> env = <String, String>{
      'PYTHONUTF8': '1',
      'PYTHONIOENCODING': 'utf-8',
    };
    if (Platform.isWindows) return env;
    final List<String> cur =
        (Platform.environment['PATH'] ?? '').split(':').where((String p) => p.isNotEmpty).toList();
    final List<String> extra =
        _extraPathDirs().where((String d) => !cur.contains(d)).toList();
    if (extra.isNotEmpty) env['PATH'] = <String>[...cur, ...extra].join(':');
    return env;
  }

  static List<String> _extraPathDirs() {
    final String home = Platform.environment['HOME'] ?? '';
    final List<String> dirs = <String>[
      if (Platform.isMacOS) ...<String>[
        '/opt/homebrew/bin', // Homebrew on Apple Silicon
        '/usr/local/bin', // Homebrew on Intel, python.org's symlinks
        '/Library/Frameworks/Python.framework/Versions/Current/bin', // python.org
        ..._userPythonBins(home), // pip install --user scripts
      ],
      if (home.isNotEmpty) '$home/.local/bin', // pipx (both), pip --user (Linux)
    ];
    return dirs.where((String d) => Directory(d).existsSync()).toList();
  }

  static List<String> _userPythonBins(String home) {
    if (home.isEmpty) return const <String>[];
    try {
      final Directory d = Directory('$home/Library/Python');
      if (!d.existsSync()) return const <String>[];
      return d
          .listSync()
          .whereType<Directory>()
          .map((Directory e) => '${e.path}/bin')
          .toList();
    } on FileSystemException {
      return const <String>[];
    }
  }

  /// "Python 3.12.8" -> true for 3.11+.
  static bool _pythonNewEnough(String versionLine) {
    final Match? m = RegExp(r'(\d+)\.(\d+)').firstMatch(versionLine);
    if (m == null) return false;
    final int major = int.parse(m[1]!), minor = int.parse(m[2]!);
    return major > 3 || (major == 3 && minor >= 11);
  }

  /// Runs [executable] [args] like [Process.run], but gives up and kills the
  /// process after [timeout] instead of hanging forever. Needed because a
  /// Windows "App Execution Alias" stub (the `python`/`python3`/`py.exe`
  /// placeholders Windows ships even with no Python installed, meant to
  /// redirect first use to the Microsoft Store) doesn't reliably exit right
  /// away on every machine — without this, a probe hitting one just sits
  /// there, and the setup screen's spinner never resolves either way
  /// (reported as the whole check "keeps reloading" and never finishing).
  /// Returns null on timeout or if the executable isn't found at all.
  static Future<ProcessResult?> _runWithTimeout(
    String executable,
    List<String> args, {
    Duration timeout = const Duration(seconds: 10),
    Map<String, String>? environment,
  }) async {
    Process proc;
    try {
      proc = await Process.start(executable, args,
          runInShell: true, environment: environment, includeParentEnvironment: true);
    } on ProcessException {
      return null;
    }
    const Utf8Decoder dec = Utf8Decoder(allowMalformed: true);
    final Future<String> stdoutF = proc.stdout.transform(dec).join();
    final Future<String> stderrF = proc.stderr.transform(dec).join();
    try {
      final int code = await proc.exitCode.timeout(timeout);
      return ProcessResult(proc.pid, code, await stdoutF, await stderrF);
    } on TimeoutException {
      proc.kill();
      return null;
    }
  }

  Future<bool> resolve() async {
    for (final CliResolution c in _candidates) {
      final ProcessResult? r = await _runWithTimeout(
        c.executable,
        <String>[...c.prefixArgs, '--version'],
        environment: _env,
      );
      if (r != null && r.exitCode == 0) {
        _resolved = c;
        _version = '${r.stdout}'.trim();
        return true;
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

  /// Same source, as a pip VCS spec -- what `pipx install` (and the README's
  /// manual fallback) use instead of the zipball URL.
  static const String gitUrl =
      'git+https://github.com/kevinisgoated24-spec/OCforge.git';

  /// The first Python 3.11+ that answers `--version`, or null if there's none.
  /// Older ones are skipped (and reported through [tooOld]) rather than
  /// returned: pip would just refuse ocforge's `requires-python` later with
  /// a far less obvious error.
  static Future<PythonInfo?> findPython({void Function(String)? tooOld}) async {
    final List<List<String>> probes = <List<String>>[
      if (Platform.isWindows) <String>['py', '-3'],
      if (!Platform.isWindows)
        for (final String v in _pythonVersions) <String>['python$v'],
      <String>['python3'],
      <String>['python'],
    ];
    for (final List<String> p in probes) {
      final ProcessResult? r = await _runWithTimeout(
          p.first, <String>[...p.skip(1), '--version'],
          environment: _env);
      if (r == null) continue; // timed out, or not found at all -- next probe
      final String v = ('${r.stdout}${r.stderr}').trim();
      // The Microsoft Store stub usually exits non-zero and prints an install
      // hint; on machines where it doesn't exit promptly, the timeout above
      // catches it instead.
      if (r.exitCode == 0 && v.toLowerCase().startsWith('python')) {
        if (!_pythonNewEnough(v)) {
          tooOld?.call('${p.first}: $v is too old (ocforge needs 3.11+) — skipping');
          continue;
        }
        return PythonInfo(p.first, p.skip(1).toList(), v);
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
        environment: _env,
      );
      log('${ep.stdout}${ep.stderr}'.trim());
      if (ep.exitCode == 0) {
        (code, managed) = await pip(const <String>[]);
        if (managed) {
          (code, managed) = await pip(const <String>['--break-system-packages']);
        }
      }
    }
    if (code != 0) {
      // Last resort. Arch and its family (CachyOS, Manjaro, EndeavourOS, …)
      // don't ship pip with Python at all -- ensurepip's own bootstrap then
      // hits the exact same PEP 668 "externally-managed-environment" guard
      // trying to install itself system-wide, with no --break-system-packages
      // equivalent exposed on ensurepip's own CLI to get past it. pipx
      // sidesteps all of this: its installs live in their own venv, never
      // "the system Python", so PEP 668 never applies. It's also already
      // this project's own documented manual fallback (see the demo-mode
      // banner / README), so trying it here is the same advice, automated.
      log('');
      log('pip install still failing — trying pipx instead …');
      code = await _installViaPipx(log);
    }
    return code;
  }

  static Future<String?> _findPipx() async {
    try {
      final ProcessResult r =
          await Process.run('pipx', const <String>['--version'],
              runInShell: true, environment: _env);
      if (r.exitCode == 0) return 'pipx';
    } on ProcessException {
      // not on PATH
    }
    return null;
  }

  static Future<int> _installViaPipx(void Function(String) log) async {
    final String? pipx = await _findPipx();
    if (pipx == null) {
      log('pipx isn\'t installed either. On macOS: brew install pipx — '
          'on Arch/CachyOS/Manjaro: sudo pacman -S python-pipx — '
          'on Debian/Ubuntu: sudo apt install pipx — '
          'then rerun, or by hand:  pipx install "$gitUrl"');
      return 1;
    }
    final List<String> args = <String>['install', '--force', gitUrl];
    log('\$ $pipx ${args.join(' ')}');
    final Process proc = await Process.start(pipx, args,
        runInShell: true, environment: _env, includeParentEnvironment: true);
    const Utf8Decoder dec = Utf8Decoder(allowMalformed: true);
    proc.stdout.transform(dec).transform(const LineSplitter()).listen(log);
    proc.stderr.transform(dec).transform(const LineSplitter()).listen(log);
    return await proc.exitCode;
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
