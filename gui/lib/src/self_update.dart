import 'dart:convert';
import 'dart:io';

/// Downloads a newer GUI release and swaps it into place in the running
/// app's own install directory, then relaunches — the "actually auto-update"
/// half of [checkForGuiUpdate] (gui_update.dart), which only ever detects
/// and links.
///
/// A running executable can't overwrite itself (Windows locks it outright;
/// even where the OS allows it, mid-swap is not a state to leave a build in),
/// so [apply] downloads and extracts the new build into a temp dir, writes a
/// tiny platform-native relauncher script next to it, launches that script
/// **detached** with this process's pid, and returns. The relauncher waits
/// for this process to actually exit, renames the current install dir aside,
/// moves the new one into its place, deletes the backup, and starts the new
/// executable — restoring the backup instead if the swap fails partway, so a
/// failed update never leaves the app unable to launch at all. The caller is
/// expected to `exit(0)` right after a `true` return so the relauncher's
/// wait loop doesn't sit around for its full timeout.
///
/// Every step is best-effort: any failure returns `false` having touched
/// nothing under the app's install dir, so the existing "open the release
/// page" fallback (gui_update.dart's [openInBrowser]) still works.
class GuiSelfUpdate {
  static const String _releaseByTagApi =
      'https://api.github.com/repos/kevinisgoated24-spec/OCforge/releases/tags/';

  /// Asset names, matching .github/workflows/gui-build.yml's packaging step.
  static String _assetName() {
    if (Platform.isWindows) return 'OCForge-GUI-windows-x64.zip';
    if (Platform.isMacOS) return 'OCForge-GUI-macos.zip';
    return 'OCForge-GUI-linux-x64.tar.gz';
  }

  static Future<String?> _assetDownloadUrl(String tag, void Function(String) log) async {
    final HttpClient client = HttpClient()..connectionTimeout = const Duration(seconds: 10);
    try {
      final HttpClientRequest req =
          await client.getUrl(Uri.parse('$_releaseByTagApi$tag'));
      req.headers.set(HttpHeaders.userAgentHeader, 'ocforge-gui');
      req.headers.set(HttpHeaders.acceptHeader, 'application/vnd.github+json');
      final HttpClientResponse resp = await req.close();
      if (resp.statusCode != 200) {
        log('release lookup failed (HTTP ${resp.statusCode})');
        return null;
      }
      final String body = await resp.transform(utf8.decoder).join();
      final Map<String, dynamic> json = jsonDecode(body) as Map<String, dynamic>;
      final String want = _assetName();
      for (final dynamic a in (json['assets'] as List<dynamic>? ?? <dynamic>[])) {
        final Map<String, dynamic> asset = a as Map<String, dynamic>;
        if (asset['name'] == want) return asset['browser_download_url'] as String?;
      }
      log('release $tag has no $want asset');
      return null;
    } on Object catch (e) {
      log('release lookup failed: $e');
      return null;
    } finally {
      client.close(force: true);
    }
  }

  static Future<bool> _download(String url, File dest, void Function(String) log) async {
    final HttpClient client = HttpClient()..connectionTimeout = const Duration(seconds: 15);
    try {
      final HttpClientRequest req = await client.getUrl(Uri.parse(url));
      req.headers.set(HttpHeaders.userAgentHeader, 'ocforge-gui');
      final HttpClientResponse resp = await req.close();
      if (resp.statusCode != 200) {
        log('download failed (HTTP ${resp.statusCode})');
        return false;
      }
      final IOSink sink = dest.openWrite();
      await resp.pipe(sink);
      return true;
    } on Object catch (e) {
      log('download failed: $e');
      return false;
    } finally {
      client.close(force: true);
    }
  }

  /// Shells out to the OS's own archive tool rather than pulling in a zip/tar
  /// package — one less dependency, and these are always present on the
  /// three build targets (PowerShell 5.1+/Expand-Archive on Windows, the
  /// system `unzip` on macOS, `tar` everywhere Linux ships).
  static Future<bool> _extract(File archive, Directory dest) async {
    try {
      ProcessResult r;
      if (Platform.isWindows) {
        r = await Process.run('powershell.exe', <String>[
          '-NoProfile', '-NonInteractive', '-Command',
          'Expand-Archive -LiteralPath "${archive.path}" -DestinationPath '
              '"${dest.path}" -Force',
        ]);
      } else if (Platform.isMacOS) {
        r = await Process.run('unzip', <String>['-oq', archive.path, '-d', dest.path]);
      } else {
        r = await Process.run('tar', <String>['xzf', archive.path, '-C', dest.path]);
      }
      return r.exitCode == 0;
    } on ProcessException {
      return false;
    }
  }

  static String _join(Iterable<String> parts) => parts.join(Platform.pathSeparator);

  /// Downloads+extracts the [tag] release, stages the relauncher, and starts
  /// it detached. Returns true iff the relauncher is now running and waiting
  /// — the caller should `exit(0)` shortly after.
  static Future<bool> apply({required String tag, required void Function(String) log}) async {
    try {
      final Directory stage = await Directory.systemTemp.createTemp('ocforge_gui_update_');

      log('looking up the $tag release…');
      final String? url = await _assetDownloadUrl(tag, log);
      if (url == null) return false;

      final String assetName = _assetName();
      final File archive = File(_join(<String>[stage.path, assetName]));
      log('downloading $assetName…');
      if (!await _download(url, archive, log)) return false;

      final Directory extracted = Directory(_join(<String>[stage.path, 'extracted']));
      await extracted.create(recursive: true);
      log('extracting…');
      if (!await _extract(archive, extracted)) {
        log('extraction failed (missing unzip/tar/PowerShell?)');
        return false;
      }

      final String currentExe = Platform.resolvedExecutable;
      final String exeName = currentExe.split(Platform.pathSeparator).last;
      final String src;
      final String dest;
      final String newExe;

      if (Platform.isMacOS) {
        final FileSystemEntity? app = extracted
            .listSync()
            .cast<FileSystemEntity?>()
            .firstWhere((FileSystemEntity? e) => e != null && e.path.endsWith('.app'),
                orElse: () => null);
        if (app == null) {
          log('no .app bundle in the downloaded archive');
          return false;
        }
        src = app!.path;
        final List<String> parts = currentExe.split(Platform.pathSeparator);
        final int macIdx = parts.lastIndexOf('MacOS');
        if (macIdx < 2) {
          log('unexpected executable path: $currentExe');
          return false;
        }
        // .../<App>.app/Contents/MacOS/<exe> -> the .app dir is 2 up from MacOS/
        dest = _join(parts.sublist(0, macIdx - 1));
        newExe = _join(<String>[dest, 'Contents', 'MacOS', exeName]);
      } else {
        src = extracted.path;
        dest = File(currentExe).parent.path;
        newExe = _join(<String>[dest, exeName]);
      }

      final String scriptPath = await _writeRelauncher(stage);
      log('starting the relauncher…');
      if (Platform.isWindows) {
        await Process.start(
          'powershell.exe',
          <String>[
            '-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden',
            '-ExecutionPolicy', 'Bypass', '-File', scriptPath,
            '-ProcId', '$pid', '-Src', src, '-Dest', dest, '-Exe', newExe,
          ],
          mode: ProcessStartMode.detached,
        );
      } else {
        await Process.start(
          '/bin/sh',
          <String>[scriptPath, '$pid', src, dest, newExe],
          mode: ProcessStartMode.detached,
        );
      }
      return true;
    } on Object catch (e) {
      log('self-update failed: $e');
      return false;
    }
  }

  static Future<String> _writeRelauncher(Directory stage) async {
    if (Platform.isWindows) {
      final File f = File(_join(<String>[stage.path, 'relaunch.ps1']));
      await f.writeAsString(_windowsRelauncher);
      return f.path;
    }
    final File f = File(_join(<String>[stage.path, 'relaunch.sh']));
    await f.writeAsString(_unixRelauncher);
    return f.path;
  }
}

// Backs up the current install dir before moving the new one in, and
// restores it if the swap doesn't fully complete — a failed update should
// never leave the app unable to launch. Self-deletes as its last act; the
// script has already been fully read by the interpreter by then, so this is
// safe on every target platform. `-Src`/`-Dest` are directories (Windows/
// Linux: the folder holding the exe; macOS: the .app bundle itself).
const String _windowsRelauncher = r'''
param(
  [Parameter(Mandatory=$true)][int]$ProcId,
  [Parameter(Mandatory=$true)][string]$Src,
  [Parameter(Mandatory=$true)][string]$Dest,
  [Parameter(Mandatory=$true)][string]$Exe
)

for ($i = 0; $i -lt 60; $i++) {
  if (-not (Get-Process -Id $ProcId -ErrorAction SilentlyContinue)) { break }
  Start-Sleep -Seconds 1
}

$old = "$Dest.ocforge-old"
if (Test-Path $old) { Remove-Item -Recurse -Force $old -ErrorAction SilentlyContinue }

$ok = $false
for ($i = 0; $i -lt 30; $i++) {
  try {
    Move-Item -Path $Dest -Destination $old -ErrorAction Stop
    Move-Item -Path $Src -Destination $Dest -ErrorAction Stop
    $ok = $true
    break
  } catch {
    Start-Sleep -Seconds 1
  }
}

if (-not $ok -and (Test-Path $old) -and -not (Test-Path $Dest)) {
  Move-Item -Path $old -Destination $Dest -ErrorAction SilentlyContinue
}
if (Test-Path $old) { Remove-Item -Recurse -Force $old -ErrorAction SilentlyContinue }
if (Test-Path $Dest) { Start-Process -FilePath $Exe }

Remove-Item -Force $MyInvocation.MyCommand.Path -ErrorAction SilentlyContinue
''';

const String _unixRelauncher = r'''
#!/bin/sh
PID="$1"; SRC="$2"; DEST="$3"; EXE="$4"

i=0
while kill -0 "$PID" 2>/dev/null; do
  i=$((i + 1))
  [ "$i" -gt 60 ] && break
  sleep 1
done

OLD="$DEST.ocforge-old"
rm -rf "$OLD"

ok=0
i=0
while [ "$i" -lt 30 ]; do
  if mv "$DEST" "$OLD" 2>/dev/null && mv "$SRC" "$DEST" 2>/dev/null; then
    ok=1
    break
  fi
  i=$((i + 1))
  sleep 1
done

if [ "$ok" -ne 1 ] && [ -d "$OLD" ] && [ ! -e "$DEST" ]; then
  mv "$OLD" "$DEST" 2>/dev/null
fi
rm -rf "$OLD"

if [ -e "$DEST" ]; then
  if [ "$(uname)" = "Darwin" ]; then
    xattr -dr com.apple.quarantine "$DEST" 2>/dev/null
  fi
  chmod +x "$EXE" 2>/dev/null
  nohup "$EXE" >/dev/null 2>&1 &
fi
rm -f "$0"
''';
