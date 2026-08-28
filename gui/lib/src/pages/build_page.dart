// ignore_for_file: use_build_context_synchronously

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';

import '../controller.dart';
import '../demo.dart';
import '../widgets.dart';

class BuildPage extends StatefulWidget {
  const BuildPage({super.key});

  @override
  State<BuildPage> createState() => _BuildPageState();
}

class _BuildPageState extends State<BuildPage> {
  final TextEditingController _outCtl = TextEditingController();
  final List<String> _log = <String>[];
  bool _running = false;
  bool _recovery = true;
  bool _dumpDsdt = false;
  bool _debug = false;
  bool _legacyMmap = false;
  int? _lastExit;
  Process? _proc;

  @override
  void dispose() {
    _outCtl.dispose();
    _proc?.kill();
    super.dispose();
  }

  void _append(String line) {
    if (!mounted) return;
    setState(() => _log.add(line));
  }

  Future<void> _forge() async {
    final OcforgeController c = ControllerScope.of(context);
    if (c.specPath == null) {
      _snack('Detect or open a spec first');
      return;
    }
    final String out = _outCtl.text.trim();
    if (out.isEmpty) {
      _snack('Type an output folder path');
      return;
    }
    setState(() {
      _running = true;
      _lastExit = null;
      _log.clear();
    });

    if (c.demo) {
      await _demoRun(out);
      return;
    }

    final List<String> args = <String>[
      'build',
      '--spec',
      c.specPath!,
      '--out',
      out,
      if (c.macosOverride != null) ...<String>['--macos', '${c.macosOverride}'],
      if (_recovery) '--recovery',
      if (_dumpDsdt) '--dump-dsdt',
      if (_debug) '--debug',
      if (_legacyMmap) '--legacy-mmap',
    ];
    _append('\$ ocforge ${args.join(' ')}\n');
    try {
      final Process proc = await c.cli.start(args);
      _proc = proc;
      const Utf8Decoder dec = Utf8Decoder(allowMalformed: true);
      final StreamSubscription<String> s1 = proc.stdout
          .transform(dec)
          .transform(const LineSplitter())
          .listen(_append);
      final StreamSubscription<String> s2 = proc.stderr
          .transform(dec)
          .transform(const LineSplitter())
          .listen(_append);
      final int code = await proc.exitCode;
      await s1.cancel();
      await s2.cancel();
      _finish(code, out);
    } catch (e) {
      _append('\n$e');
      _finish(-1, out);
    }
  }

  Future<void> _demoRun(String out) async {
    _append('\$ ocforge build --spec (demo) --out $out'
        '${_recovery ? ' --recovery' : ''}\n');
    final List<String> lines = <String>[
      ...demoBuildLog,
      if (_recovery) ...<String>[
        '',
        'downloading macOS 15 recovery (this is the slow part) …',
        '  recovery staged at $out/com.apple.recovery.boot',
      ],
    ];
    for (final String line in lines) {
      if (!mounted || !_running) return;
      await Future<void>.delayed(const Duration(milliseconds: 150));
      _append(line);
    }
    _finish(0, out);
  }

  void _finish(int code, String out) {
    _proc = null;
    if (!mounted) return;
    setState(() {
      _running = false;
      _lastExit = code;
    });
    final bool ok = code == 0;
    _append(ok
        ? '\n\u2713 done \u2014 EFI written under $out'
        : '\n\u2717 build failed (exit $code)');
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        behavior: SnackBarBehavior.floating,
        shape:
            RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
        content: Text(ok ? 'EFI build finished' : 'Build failed \u2014 see the log'),
        action: ok
            ? SnackBarAction(label: 'Open folder', onPressed: () => _openFolder(out))
            : null,
      ),
    );
  }

  Future<void> _openFolder(String path) async {
    try {
      if (Platform.isWindows) {
        await Process.run('explorer', <String>[path], runInShell: true);
      } else if (Platform.isMacOS) {
        await Process.run('open', <String>[path]);
      } else {
        await Process.run('xdg-open', <String>[path]);
      }
    } on ProcessException {
      // best effort
    }
  }

  void _cancel() {
    _proc?.kill();
    _append('\n(cancelled)');
    _finish(130, _outCtl.text.trim());
  }

  void _snack(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        behavior: SnackBarBehavior.floating,
        shape:
            RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
        content: Text(msg),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final OcforgeController c = ControllerScope.of(context);

    return PageScroller(
      children: <Widget>[
        FadeInUp(
          child: SectionTitle(
            'Forge the EFI',
            subtitle:
                'Downloads OpenCore, the resolved kexts and SSDTs, assembles config.plist, writes an EFI/ folder, '
                'and (by default) stages a macOS recovery image beside it.',
          ),
        ),
        const SizedBox(height: 22),
        FadeInUp(
          delay: const Duration(milliseconds: 60),
          child: ExpressiveCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                const CardHeader(Icons.folder_rounded, 'Output folder'),
                const SizedBox(height: 14),
                TextField(
                  controller: _outCtl,
                  decoration: InputDecoration(
                    hintText: r'e.g. C:\Users\you\Desktop\EFI',
                    filled: true,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(16),
                      borderSide: BorderSide.none,
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Stage a macOS recovery image'),
                  subtitle: const Text(
                      'com.apple.recovery.boot next to EFI/ \u2014 downloads from Apple, slow \u2014 --recovery'),
                  value: _recovery,
                  onChanged:
                      _running ? null : (bool v) => setState(() => _recovery = v),
                ),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Build SSDTs from this PC\u2019s DSDT'),
                  subtitle: const Text(
                      'Runs SSDTTime against the live ACPI tables (Linux host) \u2014 --dump-dsdt'),
                  value: _dumpDsdt,
                  onChanged: _running ? null : (bool v) => setState(() => _dumpDsdt = v),
                ),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('OpenCore DEBUG build'),
                  subtitle: const Text('Verbose logging to the EFI \u2014 --debug'),
                  value: _debug,
                  onChanged: _running ? null : (bool v) => setState(() => _debug = v),
                ),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Legacy memory map'),
                  subtitle: const Text(
                      'EnableWriteUnprotector instead of RebuildAppleMemoryMap \u2014 for '
                      'OEM firmware (Dell/HP/Lenovo) that panics early \u2014 --legacy-mmap'),
                  value: _legacyMmap,
                  onChanged: _running ? null : (bool v) => setState(() => _legacyMmap = v),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 18),
        FadeInUp(
          delay: const Duration(milliseconds: 100),
          child: Row(
            children: <Widget>[
              HeroButton(
                label: _running ? 'Forging\u2026' : 'Forge EFI',
                icon: Icons.local_fire_department_rounded,
                busy: _running,
                onPressed: _running ? null : _forge,
              ),
              const SizedBox(width: 12),
              if (_running)
                OutlinedButton.icon(
                  onPressed: _cancel,
                  icon: const Icon(Icons.stop_rounded),
                  label: const Text('Cancel'),
                ),
              const Spacer(),
              if (c.specLabel != null)
                SpecChip('spec', c.specLabel!, icon: Icons.description_outlined),
            ],
          ),
        ),
        const SizedBox(height: 10),
        if (_running) const LinearProgressIndicator(),
        const SizedBox(height: 18),
        FadeInUp(
          delay: const Duration(milliseconds: 140),
          child: LogConsole(lines: _log, minHeight: 300),
        ),
        if (_lastExit == 0) ...<Widget>[
          const SizedBox(height: 14),
          Row(
            children: <Widget>[
              FilledButton.tonalIcon(
                onPressed: _running ? null : () => _validate(_outCtl.text.trim()),
                icon: const Icon(Icons.verified_rounded),
                label: const Text('Validate this EFI'),
              ),
              const SizedBox(width: 12),
              Flexible(
                child: Text('runs OpenCore’s ocvalidate on the config.plist',
                    style: TextStyle(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                        fontSize: 12.5)),
              ),
            ],
          ),
        ],
      ],
    );
  }

  Future<void> _validate(String out) async {
    final OcforgeController c = ControllerScope.of(context);
    if (out.isEmpty) return;
    setState(() => _running = true);
    _append('\n\$ ocforge validate --efi $out');
    int code = -1;
    if (c.demo) {
      for (final String l in demoValidateOutput) {
        if (!mounted) return;
        await Future<void>.delayed(const Duration(milliseconds: 120));
        _append(l);
      }
      code = 0;
    } else {
      try {
        final proc = await c.cli.start(<String>['validate', '--efi', out]);
        const Utf8Decoder dec = Utf8Decoder(allowMalformed: true);
        final StreamSubscription<String> s1 =
            proc.stdout.transform(dec).transform(const LineSplitter()).listen(_append);
        final StreamSubscription<String> s2 =
            proc.stderr.transform(dec).transform(const LineSplitter()).listen(_append);
        code = await proc.exitCode;
        await s1.cancel();
        await s2.cancel();
      } catch (e) {
        _append('\n$e');
      }
    }
    _append(code == 0 ? '\n✓ ocvalidate: no issues' : '\n✗ ocvalidate exit $code');
    if (mounted) {
      setState(() => _running = false);
      _snack(code == 0 ? 'ocvalidate: no issues' : 'ocvalidate found problems — see the log');
    }
  }
}
