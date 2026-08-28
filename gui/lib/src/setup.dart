// ignore_for_file: use_build_context_synchronously

import 'dart:io';

import 'package:flutter/material.dart';

import 'cli.dart';
import 'controller.dart';
import 'widgets.dart';

/// Wraps the app. On first launch it checks for Python + the `ocforge` CLI and,
/// if either is missing, shows a one-screen installer before handing off to
/// [child]. "Skip" drops straight into demo mode.
class SetupGate extends StatefulWidget {
  const SetupGate({super.key, required this.child});

  final Widget child;

  @override
  State<SetupGate> createState() => _SetupGateState();
}

enum _Phase { checking, needsSetup, working, restartNeeded, ready }

class _SetupGateState extends State<SetupGate> {
  _Phase _phase = _Phase.checking;
  PythonInfo? _python;
  bool _ocforge = false;
  final List<String> _log = <String>[];

  @override
  void initState() {
    super.initState();
    _check();
  }

  void _say(String s) {
    if (mounted) setState(() => _log.add(s));
  }

  String get _pythonHint {
    if (Platform.isMacOS) {
      return 'Install Python 3.11+ (brew install python, or python.org), then reopen OCForge.';
    }
    if (Platform.isLinux) {
      return 'Install Python 3.11+ (e.g. sudo apt install python3 python3-pip), then reopen OCForge.';
    }
    return 'Install Python 3.11+ from https://www.python.org/downloads/ '
        '(tick "Add to PATH"), then reopen OCForge.';
  }

  Future<void> _check() async {
    setState(() => _phase = _Phase.checking);
    final OcforgeController c = ControllerScope.of(context);
    await c.init(); // re-resolves the CLI
    _python = await OcforgeCli.findPython();
    _ocforge = c.cliReady;
    if (!mounted) return;
    setState(() {
      _phase = _ocforge ? _Phase.ready : _Phase.needsSetup;
    });
  }

  Future<void> _install() async {
    setState(() {
      _phase = _Phase.working;
      _log.clear();
    });

    // 1. Python
    if (_python == null) {
      if (Platform.isWindows) {
        _say('Python not found — installing via winget …');
        final int code = await OcforgeCli.wingetInstallPython(_say);
        _python = await OcforgeCli.findPython();
        if (_python == null) {
          _say('');
          _say(code == -1
              ? 'Could not install Python automatically. $_pythonHint'
              : 'Python was installed but this session can\'t see it yet. '
                  'Close and reopen OCForge to finish setup.');
          setState(() => _phase = _Phase.restartNeeded);
          return;
        }
        _say('found ${_python!.version}');
      } else {
        _say('Python not found.');
        _say(_pythonHint);
        setState(() => _phase = _Phase.restartNeeded);
        return;
      }
    } else {
      _say('found ${_python!.version}');
    }

    // 2. ocforge
    _say('');
    _say('Installing the ocforge CLI …');
    final int code = await OcforgeCli.installOcforge(_python!, _say);
    _say('');
    if (code != 0) {
      _say('pip exited $code — see the log above. You can retry, or install '
          'it yourself:  pip install --user "${OcforgeCli.zipballUrl}"');
      setState(() => _phase = _Phase.needsSetup);
      return;
    }

    // 3. re-resolve
    final OcforgeController c = ControllerScope.of(context);
    await c.init();
    if (!mounted) return;
    if (c.cliReady) {
      _say('${c.cli.version.isEmpty ? 'ocforge' : c.cli.version} ready — continuing.');
      setState(() => _phase = _Phase.ready);
    } else {
      _say('Installed, but the CLI still isn\'t resolving. Reopen OCForge.');
      setState(() => _phase = _Phase.restartNeeded);
    }
  }

  void _skip() => setState(() => _phase = _Phase.ready);

  @override
  Widget build(BuildContext context) {
    if (_phase == _Phase.ready) return widget.child;

    final ColorScheme s = Theme.of(context).colorScheme;
    final bool busy = _phase == _Phase.working || _phase == _Phase.checking;

    return Scaffold(
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 640),
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(40),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Row(
                  children: <Widget>[
                    const AppGlyph(size: 44),
                    const SizedBox(width: 16),
                    Text('First-run setup',
                        style: Theme.of(context).textTheme.headlineMedium),
                  ],
                ),
                const SizedBox(height: 10),
                Text(
                  'OCForge drives the ocforge Python CLI. Let’s make sure it’s here.',
                  style: TextStyle(color: s.onSurfaceVariant),
                ),
                const SizedBox(height: 24),
                _CheckRow(
                  label: 'Python 3.11+',
                  ok: _python != null,
                  detail: _python?.version ?? 'not found',
                  pending: _phase == _Phase.checking,
                ),
                const SizedBox(height: 10),
                _CheckRow(
                  label: 'ocforge CLI',
                  ok: _ocforge,
                  detail: _ocforge ? 'installed' : 'not found',
                  pending: _phase == _Phase.checking,
                ),
                const SizedBox(height: 24),
                if (_log.isNotEmpty) ...<Widget>[
                  LogConsole(lines: _log, minHeight: 160),
                  const SizedBox(height: 20),
                ],
                if (_phase == _Phase.restartNeeded)
                  FilledButton.icon(
                    onPressed: () => exit(0),
                    icon: const Icon(Icons.power_settings_new_rounded),
                    label: const Text('Quit OCForge'),
                  )
                else
                  Wrap(
                    spacing: 12,
                    runSpacing: 12,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: <Widget>[
                      HeroButton(
                        label: busy ? 'Working…' : 'Install & continue',
                        icon: Icons.download_rounded,
                        busy: busy,
                        onPressed: busy ? null : _install,
                      ),
                      OutlinedButton.icon(
                        onPressed: busy ? null : () => _check(),
                        icon: const Icon(Icons.refresh_rounded),
                        label: const Text('Recheck'),
                      ),
                      TextButton(
                        onPressed: busy ? null : _skip,
                        child: const Text('Skip — use demo mode'),
                      ),
                    ],
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _CheckRow extends StatelessWidget {
  const _CheckRow({
    required this.label,
    required this.ok,
    required this.detail,
    this.pending = false,
  });

  final String label;
  final bool ok;
  final String detail;
  final bool pending;

  @override
  Widget build(BuildContext context) {
    final ColorScheme s = Theme.of(context).colorScheme;
    final Widget mark = pending
        ? const SizedBox(
            width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2.4))
        : Icon(
            ok ? Icons.check_circle_rounded : Icons.cancel_rounded,
            color: ok ? s.primary : s.error,
          );
    return ExpressiveCard(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
      child: Row(
        children: <Widget>[
          mark,
          const SizedBox(width: 14),
          Text(label, style: const TextStyle(fontWeight: FontWeight.w600)),
          const Spacer(),
          Flexible(
            child: Text(detail,
                textAlign: TextAlign.right,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(color: s.onSurfaceVariant, fontSize: 12.5)),
          ),
        ],
      ),
    );
  }
}
