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

enum _DsdtSource { none, autoDump, supplied }

class _BuildPageState extends State<BuildPage> {
  final TextEditingController _outCtl = TextEditingController();
  final TextEditingController _dsdtPathCtl = TextEditingController();
  final TextEditingController _excludeKextCtl = TextEditingController();
  final TextEditingController _includeKextCtl = TextEditingController();
  final TextEditingController _excludeSsdtCtl = TextEditingController();
  final TextEditingController _smbiosCtl = TextEditingController();
  final TextEditingController _quirkCtl = TextEditingController();
  final TextEditingController _spoofDeviceCtl = TextEditingController();
  final List<String> _log = <String>[];
  bool _running = false;
  bool _recovery = true;
  _DsdtSource _dsdtSource = _DsdtSource.none;
  bool _debug = false;
  bool _legacyMmap = false;
  bool _offlineInstaller = false;
  bool _forceUnsupportedGpu = false;
  bool _forceUnsupportedOs = false;
  bool _advancedOpen = false;
  int? _lastExit;
  Process? _proc;

  @override
  void dispose() {
    _outCtl.dispose();
    _dsdtPathCtl.dispose();
    _excludeKextCtl.dispose();
    _includeKextCtl.dispose();
    _excludeSsdtCtl.dispose();
    _smbiosCtl.dispose();
    _quirkCtl.dispose();
    _spoofDeviceCtl.dispose();
    _proc?.kill();
    super.dispose();
  }

  /// Splits a comma/space-separated field into individual tokens (kext/SSDT
  /// names, or NAME=value quirk pairs).
  List<String> _splitNames(String raw) => raw
      .split(RegExp(r'[,\s]+'))
      .map((String s) => s.trim())
      .where((String s) => s.isNotEmpty)
      .toList();

  /// Splits a field one entry per line -- used only for --spoof-device,
  /// since an OC device path itself contains commas (e.g. "Pci(0x3,0x0)"),
  /// so comma-splitting like [_splitNames] would break a single entry apart.
  List<String> _splitLines(String raw) => raw
      .split('\n')
      .map((String s) => s.trim())
      .where((String s) => s.isNotEmpty)
      .toList();

  /// Pulls the warning/failure lines back out of the raw build log --
  /// matches the "  ! thing" prefix `_print_build_report` (cli.py) already
  /// uses for kext/SSDT download failures, manual-TODOs and the placeholder-
  /// SMBIOS warning, plus the final "✗ build failed" line -- so the
  /// summary card below doesn't need its own separate log format.
  List<String> _extractIssues() => _log
      .map((String l) => l.trim())
      .where((String l) => l.startsWith('!') || l.startsWith('✗'))
      .toList();

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

    final String dsdtPath = _dsdtPathCtl.text.trim();
    final List<String> excludeKexts = _splitNames(_excludeKextCtl.text);
    final List<String> includeKexts = _splitNames(_includeKextCtl.text);
    final List<String> excludeSsdts = _splitNames(_excludeSsdtCtl.text);
    final List<String> quirks = _splitNames(_quirkCtl.text);
    final List<String> spoofDevices = _splitLines(_spoofDeviceCtl.text);
    final String smbios = _smbiosCtl.text.trim();
    final List<String> args = <String>[
      _offlineInstaller ? 'offline-installer' : 'build',
      '--spec',
      c.specPath!,
      '--out',
      out,
      if (c.macosOverride != null) ...<String>['--macos', '${c.macosOverride}'],
      // offline-installer always stages its own recovery boot image (with
      // the Sonoma+ older-BaseSystem split) and doesn't take these flags.
      if (!_offlineInstaller && _recovery) '--recovery',
      if (!_offlineInstaller && _dsdtSource == _DsdtSource.autoDump) '--dump-dsdt',
      if (!_offlineInstaller && _dsdtSource == _DsdtSource.supplied && dsdtPath.isNotEmpty)
        ...<String>['--dsdt', dsdtPath],
      if (!_offlineInstaller && _debug) '--debug',
      if (_legacyMmap) '--legacy-mmap',
      if (_forceUnsupportedGpu) '--force-unsupported-gpu',
      if (_forceUnsupportedOs) '--force-unsupported-os',
      for (final String name in excludeKexts) ...<String>['--exclude-kext', name],
      for (final String name in includeKexts) ...<String>['--include-kext', name],
      for (final String name in excludeSsdts) ...<String>['--exclude-ssdt', name],
      if (smbios.isNotEmpty) ...<String>['--smbios', smbios],
      for (final String pair in quirks) ...<String>['--quirk', pair],
      for (final String pair in spoofDevices) ...<String>['--spoof-device', pair],
    ];
    try {
      int code = await _runStreamed(c, args);
      // Already forced up front (the Advanced toggles above) -> a matching
      // exit code here means something else is wrong, not "ask the user" --
      // showing the same confirm dialog again would just re-force a flag
      // that's already on the command line.
      if (code == unsupportedGpuExitCode && !_forceUnsupportedGpu) {
        final String detail = _log.join('\n');
        if (!await confirmUnsupportedGpu(context, detail)) {
          _finish(130, out);
          return;
        }
        code = await _runStreamed(c, <String>[...args, '--force-unsupported-gpu']);
      } else if (code == unsupportedOsExitCode && !_forceUnsupportedOs) {
        final String detail = _log.join('\n');
        if (!await confirmUnsupportedOs(context, detail)) {
          _finish(130, out);
          return;
        }
        code = await _runStreamed(c, <String>[...args, '--force-unsupported-os']);
      }
      _finish(code, out);
    } catch (e) {
      _append('\n$e');
      _finish(-1, out);
    }
  }

  /// Starts `ocforge <args>`, streams its output into [_log], and returns
  /// the exit code once it finishes.
  Future<int> _runStreamed(OcforgeController c, List<String> args) async {
    _append('\$ ocforge ${args.join(' ')}\n');
    final Process proc = await c.cli.start(args);
    _proc = proc;
    const Utf8Decoder dec = Utf8Decoder(allowMalformed: true);
    final StreamSubscription<String> s1 =
        proc.stdout.transform(dec).transform(const LineSplitter()).listen(_append);
    final StreamSubscription<String> s2 =
        proc.stderr.transform(dec).transform(const LineSplitter()).listen(_append);
    final int code = await proc.exitCode;
    await s1.cancel();
    await s2.cancel();
    return code;
  }

  Future<void> _demoRun(String out) async {
    final String cmd = _offlineInstaller ? 'offline-installer' : 'build';
    _append('\$ ocforge $cmd --spec (demo) --out $out'
        '${!_offlineInstaller && _recovery ? ' --recovery' : ''}\n');
    final List<String> lines = <String>[
      ...demoBuildLog,
      if (_offlineInstaller) ...<String>[
        '',
        'downloading the macOS installer via gibMacOS (this is the slow part) …',
        '  ExFAT payload staged at $out/ExFAT',
      ] else if (_recovery) ...<String>[
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
    final List<String> issues = _lastExit != null ? _extractIssues() : const <String>[];

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
                  title: const Text('Offline installer (UnPlugged)'),
                  subtitle: const Text(
                      'Also downloads the full macOS installer via gibMacOS and stages '
                      'corpnewt/UnPlugged \u2014 huge and slow, but the target machine needs '
                      'no internet during the actual install. Replaces the recovery-image '
                      'option below with its own \u2014 ocforge offline-installer'),
                  value: _offlineInstaller,
                  onChanged: _running
                      ? null
                      : (bool v) => setState(() => _offlineInstaller = v),
                ),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Stage a macOS recovery image'),
                  subtitle: const Text(
                      'com.apple.recovery.boot next to EFI/ \u2014 downloads from Apple, slow \u2014 --recovery'),
                  value: _recovery,
                  onChanged: (_running || _offlineInstaller)
                      ? null
                      : (bool v) => setState(() => _recovery = v),
                ),
                Theme(
                  data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
                  child: ExpansionTile(
                    tilePadding: EdgeInsets.zero,
                    childrenPadding: const EdgeInsets.only(bottom: 8),
                    initiallyExpanded: _advancedOpen,
                    onExpansionChanged: (bool v) => setState(() => _advancedOpen = v),
                    title: const Text('Advanced', style: TextStyle(fontWeight: FontWeight.w600)),
                    subtitle: const Text('ACPI source, debug build, memory map, forcing an '
                        'unsupported hardware/macOS combination through anyway, kext/SSDT/'
                        'SMBIOS/quirk overrides, device ID spoofing',
                        style: TextStyle(fontSize: 12.5)),
                    children: <Widget>[
                      Padding(
                        padding: const EdgeInsets.only(bottom: 4),
                        child: Text('SSDTs from', style: Theme.of(context).textTheme.labelLarge),
                      ),
                      RadioListTile<_DsdtSource>(
                        contentPadding: EdgeInsets.zero,
                        dense: true,
                        title: const Text('Dortania\u2019s precompiled set (default)'),
                        value: _DsdtSource.none,
                        groupValue: _dsdtSource,
                        onChanged: (_running || _offlineInstaller)
                            ? null
                            : (_DsdtSource? v) => setState(() => _dsdtSource = v!),
                      ),
                      RadioListTile<_DsdtSource>(
                        contentPadding: EdgeInsets.zero,
                        dense: true,
                        title: const Text('This PC\u2019s own ACPI tables'),
                        subtitle: const Text(
                            'Runs SSDTTime against a live dump \u2014 --dump-dsdt',
                            style: TextStyle(fontSize: 12)),
                        value: _DsdtSource.autoDump,
                        groupValue: _dsdtSource,
                        onChanged: (_running || _offlineInstaller)
                            ? null
                            : (_DsdtSource? v) => setState(() => _dsdtSource = v!),
                      ),
                      RadioListTile<_DsdtSource>(
                        contentPadding: EdgeInsets.zero,
                        dense: true,
                        title: const Text('A DSDT I already have'),
                        subtitle: const Text(
                            'A .aml file or a folder of dumped ACPI tables \u2014 --dsdt PATH',
                            style: TextStyle(fontSize: 12)),
                        value: _DsdtSource.supplied,
                        groupValue: _dsdtSource,
                        onChanged: (_running || _offlineInstaller)
                            ? null
                            : (_DsdtSource? v) => setState(() => _dsdtSource = v!),
                      ),
                      if (_dsdtSource == _DsdtSource.supplied)
                        Padding(
                          padding: const EdgeInsets.only(left: 8, right: 8, bottom: 8, top: 4),
                          child: TextField(
                            controller: _dsdtPathCtl,
                            enabled: !_running,
                            decoration: InputDecoration(
                              hintText: r'e.g. C:\Users\you\Desktop\my-pc-acpi',
                              isDense: true,
                              filled: true,
                              border: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(12),
                                borderSide: BorderSide.none,
                              ),
                            ),
                          ),
                        ),
                      const Divider(height: 24),
                      SwitchListTile(
                        contentPadding: EdgeInsets.zero,
                        dense: true,
                        title: const Text('OpenCore DEBUG build'),
                        subtitle: const Text('Verbose logging to the EFI \u2014 --debug'),
                        value: _debug,
                        onChanged: (_running || _offlineInstaller)
                            ? null
                            : (bool v) => setState(() => _debug = v),
                      ),
                      SwitchListTile(
                        contentPadding: EdgeInsets.zero,
                        dense: true,
                        title: const Text('Legacy memory map'),
                        subtitle: const Text(
                            'EnableWriteUnprotector instead of RebuildAppleMemoryMap \u2014 for '
                            'OEM firmware (Dell/HP/Lenovo) that panics early \u2014 --legacy-mmap',
                            style: TextStyle(fontSize: 12)),
                        value: _legacyMmap,
                        onChanged: _running ? null : (bool v) => setState(() => _legacyMmap = v),
                      ),
                      const Divider(height: 24),
                      SwitchListTile(
                        contentPadding: EdgeInsets.zero,
                        dense: true,
                        title: const Text('Force through an unsupported GPU'),
                        subtitle: const Text(
                            'Skip the \u201ccontinue anyway?\u201d prompt for no supported display '
                            'path \u2014 --force-unsupported-gpu',
                            style: TextStyle(fontSize: 12)),
                        value: _forceUnsupportedGpu,
                        onChanged: _running
                            ? null
                            : (bool v) => setState(() => _forceUnsupportedGpu = v),
                      ),
                      SwitchListTile(
                        contentPadding: EdgeInsets.zero,
                        dense: true,
                        title: const Text('Force through an unsupported macOS target'),
                        subtitle: const Text(
                            'Skip the prompt when the chosen macOS version isn\u2019t supported '
                            'on this hardware \u2014 --force-unsupported-os',
                            style: TextStyle(fontSize: 12)),
                        value: _forceUnsupportedOs,
                        onChanged: _running
                            ? null
                            : (bool v) => setState(() => _forceUnsupportedOs = v),
                      ),
                      const Divider(height: 24),
                      Padding(
                        padding: const EdgeInsets.only(bottom: 4),
                        child: Text('Kext overrides',
                            style: Theme.of(context).textTheme.labelLarge),
                      ),
                      Text(
                        'Bypasses ocforge’s hardware detection — you’re on your own '
                        'if the result doesn’t boot. Comma or space separated bundle names.',
                        style: TextStyle(
                            fontSize: 12,
                            color: Theme.of(context).colorScheme.onSurfaceVariant),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: _excludeKextCtl,
                        enabled: !_running,
                        decoration: InputDecoration(
                          labelText: 'Exclude',
                          hintText: 'e.g. USBToolBox, ECEnabler',
                          isDense: true,
                          filled: true,
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                            borderSide: BorderSide.none,
                          ),
                        ),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: _includeKextCtl,
                        enabled: !_running,
                        decoration: InputDecoration(
                          labelText: 'Include',
                          hintText: 'e.g. VoodooPS2Controller',
                          isDense: true,
                          filled: true,
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                            borderSide: BorderSide.none,
                          ),
                        ),
                      ),
                      const Divider(height: 24),
                      Padding(
                        padding: const EdgeInsets.only(bottom: 4),
                        child: Text('SSDT overrides',
                            style: Theme.of(context).textTheme.labelLarge),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: _excludeSsdtCtl,
                        enabled: !_running,
                        decoration: InputDecoration(
                          labelText: 'Exclude',
                          hintText: 'e.g. SSDT-PLUG',
                          isDense: true,
                          filled: true,
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                            borderSide: BorderSide.none,
                          ),
                        ),
                      ),
                      const Divider(height: 24),
                      Padding(
                        padding: const EdgeInsets.only(bottom: 4),
                        child: Text('SMBIOS override',
                            style: Theme.of(context).textTheme.labelLarge),
                      ),
                      Text(
                        'Use this model instead of ocforge’s own pick — macserial fails '
                        'loudly if it doesn’t actually exist.',
                        style: TextStyle(
                            fontSize: 12,
                            color: Theme.of(context).colorScheme.onSurfaceVariant),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: _smbiosCtl,
                        enabled: !_running,
                        decoration: InputDecoration(
                          labelText: 'SMBIOS model',
                          hintText: 'e.g. iMac19,1',
                          isDense: true,
                          filled: true,
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                            borderSide: BorderSide.none,
                          ),
                        ),
                      ),
                      const Divider(height: 24),
                      Padding(
                        padding: const EdgeInsets.only(bottom: 4),
                        child: Text('Quirk overrides',
                            style: Theme.of(context).textTheme.labelLarge),
                      ),
                      Text(
                        'On/off toggles only — ACPI, Booter, Kernel, or UEFI Quirks. '
                        'NAME=true or NAME=false, comma or space separated.',
                        style: TextStyle(
                            fontSize: 12,
                            color: Theme.of(context).colorScheme.onSurfaceVariant),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: _quirkCtl,
                        enabled: !_running,
                        decoration: InputDecoration(
                          labelText: 'Quirks',
                          hintText: 'e.g. DevirtualiseMmio=false',
                          isDense: true,
                          filled: true,
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                            borderSide: BorderSide.none,
                          ),
                        ),
                      ),
                      const Divider(height: 24),
                      Padding(
                        padding: const EdgeInsets.only(bottom: 4),
                        child: Text('Device ID spoof',
                            style: Theme.of(context).textTheme.labelLarge),
                      ),
                      Text(
                        'Present a different PCI device to macOS — e.g. an unsupported '
                        'GPU spoofed as a supported one. Forces the OpenCore DEBUG build '
                        'on automatically. One PATH=[VENDOR:]DEVICE per line — bypasses '
                        'ocforge’s hardware detection, you’re on your own if it doesn’t boot.',
                        style: TextStyle(
                            fontSize: 12,
                            color: Theme.of(context).colorScheme.onSurfaceVariant),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: _spoofDeviceCtl,
                        enabled: !_running,
                        maxLines: 3,
                        minLines: 1,
                        style: const TextStyle(fontFamily: 'monospace', fontSize: 12.5),
                        decoration: InputDecoration(
                          labelText: 'Device spoofs',
                          hintText: 'PciRoot(0x0)/Pci(0x3,0x0)=1002:73AF',
                          isDense: true,
                          filled: true,
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                            borderSide: BorderSide.none,
                          ),
                        ),
                      ),
                    ],
                  ),
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
        if (issues.isNotEmpty) ...<Widget>[
          const SizedBox(height: 14),
          FadeInUp(child: _BuildIssuesCard(issues: issues)),
        ],
        const SizedBox(height: 18),
        FadeInUp(
          delay: const Duration(milliseconds: 140),
          child: LogConsole(lines: _log, minHeight: 300),
        ),
        if (_lastExit == 0) ...<Widget>[
          const SizedBox(height: 14),
          Wrap(
            spacing: 12,
            runSpacing: 8,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: <Widget>[
              FilledButton.tonalIcon(
                onPressed: _running ? null : () => _validate(_outCtl.text.trim()),
                icon: const Icon(Icons.verified_rounded),
                label: const Text('Validate this EFI'),
              ),
              OutlinedButton.icon(
                onPressed: _running ? null : () => _reviewInEditor(c),
                icon: const Icon(Icons.data_object_rounded),
                label: const Text('Review in Editor'),
              ),
              Text('check or hand-tweak config.plist before it’s used to boot anything',
                  style: TextStyle(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                      fontSize: 12.5)),
            ],
          ),
        ],
      ],
    );
  }

  // Editor is nav-rail index 4 regardless of whether the dev-stats tab is
  // unlocked (that one's always appended at the end) -- see app.dart's
  // _pages/destinations.
  static const int _editorTabIndex = 4;

  void _reviewInEditor(OcforgeController c) {
    final String out = _outCtl.text.trim();
    if (out.isEmpty) return;
    final String configPath =
        <String>[out, 'EFI', 'OC', 'config.plist'].join(Platform.pathSeparator);
    c.reviewInEditor(configPath, editorTabIndex: _editorTabIndex);
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

/// Summarizes the warning/failure lines out of the full build log, so they
/// don't get lost scrolling through everything else the build printed.
class _BuildIssuesCard extends StatelessWidget {
  const _BuildIssuesCard({required this.issues});

  final List<String> issues;

  @override
  Widget build(BuildContext context) {
    final ColorScheme s = Theme.of(context).colorScheme;
    return ExpressiveCard(
      tone: s.errorContainer,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Icon(Icons.warning_amber_rounded, color: s.onErrorContainer, size: 20),
              const SizedBox(width: 10),
              Text('${issues.length} issue${issues.length == 1 ? '' : 's'} in this build',
                  style: TextStyle(
                      color: s.onErrorContainer, fontWeight: FontWeight.w700, fontSize: 14)),
            ],
          ),
          const SizedBox(height: 8),
          for (final String i in issues)
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Text(i,
                  style: TextStyle(color: s.onErrorContainer, fontSize: 12.5)),
            ),
        ],
      ),
    );
  }
}
