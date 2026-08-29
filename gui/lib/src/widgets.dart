import 'dart:io';

import 'package:flutter/material.dart';

import 'cli.dart';
import 'gui_update.dart';
import 'self_update.dart';

/// A soft entrance: fade + rise, with an optional per-item [delay] for stagger.
class FadeInUp extends StatefulWidget {
  const FadeInUp({super.key, required this.child, this.delay = Duration.zero});

  final Widget child;
  final Duration delay;

  @override
  State<FadeInUp> createState() => _FadeInUpState();
}

class _FadeInUpState extends State<FadeInUp> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 460),
  );

  @override
  void initState() {
    super.initState();
    Future<void>.delayed(widget.delay, () {
      if (mounted) _c.forward();
    });
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final Animation<double> curved =
        CurvedAnimation(parent: _c, curve: Curves.easeOutCubic);
    return AnimatedBuilder(
      animation: curved,
      builder: (BuildContext context, Widget? child) => Opacity(
        opacity: curved.value,
        child: Transform.translate(
          offset: Offset(0, 18 * (1 - curved.value)),
          child: child,
        ),
      ),
      child: widget.child,
    );
  }
}

/// Fully-rounded tonal container — the expressive "card".
class ExpressiveCard extends StatelessWidget {
  const ExpressiveCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(22),
    this.tone,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final Color? tone;

  @override
  Widget build(BuildContext context) {
    final ColorScheme s = Theme.of(context).colorScheme;
    return Container(
      decoration: BoxDecoration(
        color: tone ?? s.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(28),
      ),
      clipBehavior: Clip.antiAlias,
      child: Padding(padding: padding, child: child),
    );
  }
}

class CardHeader extends StatelessWidget {
  const CardHeader(this.icon, this.title, {super.key, this.trailing});

  final IconData icon;
  final String title;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final ColorScheme s = Theme.of(context).colorScheme;
    return Row(
      children: <Widget>[
        Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: s.secondaryContainer,
            borderRadius: BorderRadius.circular(16),
          ),
          child: Icon(icon, size: 20, color: s.onSecondaryContainer),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Text(title, style: Theme.of(context).textTheme.titleMedium),
        ),
        if (trailing != null) trailing!,
      ],
    );
  }
}

/// Label + value pill.
class SpecChip extends StatelessWidget {
  const SpecChip(this.label, this.value, {super.key, this.icon});

  final String label;
  final String value;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final ColorScheme s = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
      decoration: BoxDecoration(
        color: s.surfaceContainerHigh,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: s.outlineVariant),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          if (icon != null) ...<Widget>[
            Icon(icon, size: 15, color: s.primary),
            const SizedBox(width: 7),
          ],
          Text('$label  ',
              style: TextStyle(color: s.onSurfaceVariant, fontSize: 12.5)),
          Text(value,
              style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 12.5)),
        ],
      ),
    );
  }
}

/// The big call-to-action. Presses in slightly for an expressive bounce.
class HeroButton extends StatefulWidget {
  const HeroButton({
    super.key,
    required this.label,
    required this.icon,
    required this.onPressed,
    this.busy = false,
  });

  final String label;
  final IconData icon;
  final VoidCallback? onPressed;
  final bool busy;

  @override
  State<HeroButton> createState() => _HeroButtonState();
}

class _HeroButtonState extends State<HeroButton> {
  double _scale = 1;

  @override
  Widget build(BuildContext context) {
    final bool enabled = widget.onPressed != null && !widget.busy;
    return AnimatedScale(
      scale: _scale,
      duration: const Duration(milliseconds: 120),
      curve: Curves.easeOut,
      child: GestureDetector(
        onTapDown: enabled ? (_) => setState(() => _scale = 0.96) : null,
        onTapUp: enabled ? (_) => setState(() => _scale = 1) : null,
        onTapCancel: enabled ? () => setState(() => _scale = 1) : null,
        child: FilledButton(
          onPressed: enabled ? widget.onPressed : null,
          style: FilledButton.styleFrom(
            minimumSize: const Size(200, 60),
            shape: const StadiumBorder(),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              if (widget.busy)
                const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2.4),
                )
              else
                Icon(widget.icon),
              const SizedBox(width: 12),
              Text(widget.label, style: const TextStyle(fontSize: 16)),
            ],
          ),
        ),
      ),
    );
  }
}

class SectionTitle extends StatelessWidget {
  const SectionTitle(this.title, {super.key, this.subtitle});

  final String title;
  final String? subtitle;

  @override
  Widget build(BuildContext context) {
    final TextTheme t = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text(title, style: t.displaySmall),
        if (subtitle != null) ...<Widget>[
          const SizedBox(height: 6),
          Text(subtitle!,
              style: t.bodyLarge?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant)),
        ],
      ],
    );
  }
}

/// Monospace, auto-scrolling output view.
class LogConsole extends StatefulWidget {
  const LogConsole({super.key, required this.lines, this.minHeight = 220});

  final List<String> lines;
  final double minHeight;

  @override
  State<LogConsole> createState() => _LogConsoleState();
}

class _LogConsoleState extends State<LogConsole> {
  final ScrollController _sc = ScrollController();

  @override
  void didUpdateWidget(covariant LogConsole old) {
    super.didUpdateWidget(old);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_sc.hasClients) {
        _sc.animateTo(
          _sc.position.maxScrollExtent,
          duration: const Duration(milliseconds: 180),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  void dispose() {
    _sc.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final bool dark = Theme.of(context).brightness == Brightness.dark;
    final Color bg = dark ? const Color(0xFF14121C) : const Color(0xFF1B1830);
    return Container(
      constraints: BoxConstraints(minHeight: widget.minHeight),
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(22),
      ),
      child: widget.lines.isEmpty
          ? const Text('(no output yet)',
              style: TextStyle(color: Color(0xFF8A83A6), fontFamily: 'monospace'))
          : Scrollbar(
              controller: _sc,
              child: SingleChildScrollView(
                controller: _sc,
                child: SelectableText(
                  widget.lines.join('\n'),
                  style: const TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 12.5,
                    height: 1.5,
                    color: Color(0xFFE7E3FF),
                  ),
                ),
              ),
            ),
    );
  }
}

class AppGlyph extends StatelessWidget {
  const AppGlyph({super.key, this.size = 34});

  final double size;

  @override
  Widget build(BuildContext context) {
    final Color primary = Theme.of(context).colorScheme.primary;
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: <Color>[primary, Color.lerp(primary, Colors.white, 0.38)!],
        ),
        borderRadius: BorderRadius.circular(size * 0.32),
      ),
      alignment: Alignment.center,
      child: Text(
        'OC',
        style: TextStyle(
          color: Colors.white,
          fontWeight: FontWeight.w800,
          fontSize: size * 0.4,
          letterSpacing: -0.5,
        ),
      ),
    );
  }
}

/// Standard page frame: scrolls, pads, caps width, left-aligns.
class PageScroller extends StatelessWidget {
  const PageScroller({super.key, required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(36, 34, 36, 40),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 980),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: children,
          ),
        ),
      ),
    );
  }
}

/// The exit code `_resolve_plan` (ocforge/cli.py) uses when a build has no
/// supported display path and there was no terminal to ask "continue
/// anyway?" on — i.e. every time the GUI runs the CLI. Show
/// [confirmUnsupportedGpu] and, if the answer is yes, re-run the same
/// command with `--force-unsupported-gpu` appended.
const int unsupportedGpuExitCode = 3;

/// "Sorry, this build is unsupported. Would you still like to continue?" —
/// [detail] is the reason from the CLI's stderr. Returns true if the user
/// wants to proceed anyway (retry with `--force-unsupported-gpu`).
Future<bool> confirmUnsupportedGpu(BuildContext context, String detail) async {
  final ColorScheme s = Theme.of(context).colorScheme;
  final bool? proceed = await showDialog<bool>(
    context: context,
    builder: (BuildContext ctx) => AlertDialog(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
      icon: Icon(Icons.warning_amber_rounded, color: s.error),
      title: const Text('Sorry, this build is unsupported'),
      content: Text(
        'Would you still like to continue?\n\n$detail',
        style: TextStyle(color: s.onSurfaceVariant, fontSize: 13),
      ),
      actions: <Widget>[
        TextButton(
          onPressed: () => Navigator.pop(ctx, false),
          child: const Text('Cancel'),
        ),
        FilledButton.tonal(
          onPressed: () => Navigator.pop(ctx, true),
          child: const Text('Continue anyway'),
        ),
      ],
    ),
  );
  return proceed ?? false;
}

/// The exit code `_resolve_plan` (ocforge/cli.py) uses when an explicit
/// macOS-target override isn't actually supported on this hardware and
/// there was no terminal to ask "continue anyway?" on. Same shape as
/// [unsupportedGpuExitCode] — show [confirmUnsupportedOs] and, if the
/// answer is yes, re-run the same command with `--force-unsupported-os`.
const int unsupportedOsExitCode = 4;

/// Same dialog as [confirmUnsupportedGpu], for a forced `--macos N` that
/// isn't supported on this hardware (e.g. forcing Tahoe on a CPU generation
/// with no Tahoe iGPU driver — the build will very likely reach a desktop
/// with corrupted or missing graphics, not a clean failure). Returns true if
/// the user wants to proceed anyway (retry with `--force-unsupported-os`).
Future<bool> confirmUnsupportedOs(BuildContext context, String detail) async {
  final ColorScheme s = Theme.of(context).colorScheme;
  final bool? proceed = await showDialog<bool>(
    context: context,
    builder: (BuildContext ctx) => AlertDialog(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
      icon: Icon(Icons.warning_amber_rounded, color: s.error),
      title: const Text('This macOS version isn\'t supported here'),
      content: Text(
        'Would you still like to continue? Expect a broken or non-functional '
        'display, not a clean failure.\n\n$detail',
        style: TextStyle(color: s.onSurfaceVariant, fontSize: 13),
      ),
      actions: <Widget>[
        TextButton(
          onPressed: () => Navigator.pop(ctx, false),
          child: const Text('Cancel'),
        ),
        FilledButton.tonal(
          onPressed: () => Navigator.pop(ctx, true),
          child: const Text('Continue anyway'),
        ),
      ],
    ),
  );
  return proceed ?? false;
}

/// "A newer OCForge GUI is out — Update" — shown whenever
/// [OcforgeController.guiUpdate] finds a newer `gui-v*` release than this
/// build's [appVersion]. "Update" opens [showGuiUpdateDialog], which updates
/// both the CLI and the GUI and relaunches; if the self-update can't
/// complete for any reason it falls back to just opening the release page,
/// same as this banner always did before.
class GuiUpdateBanner extends StatelessWidget {
  const GuiUpdateBanner({super.key, required this.version, required this.url});

  final String version;
  final String url;

  @override
  Widget build(BuildContext context) {
    final ColorScheme s = Theme.of(context).colorScheme;
    return Material(
      color: s.secondaryContainer,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
        child: Row(
          children: <Widget>[
            Icon(Icons.system_update_alt_rounded, size: 18, color: s.onSecondaryContainer),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                'OCForge GUI $version is available — you have $appVersion.',
                style: TextStyle(color: s.onSecondaryContainer, fontSize: 12.5),
              ),
            ),
            TextButton(
              onPressed: () => showGuiUpdateDialog(context, version: version, url: url),
              child: const Text('Update'),
            ),
          ],
        ),
      ),
    );
  }
}

/// Confirms, then updates the `ocforge` CLI (`pip install --upgrade`) and
/// this GUI app (download + swap + relaunch — [GuiSelfUpdate]) in sequence.
/// The CLI half is independent of the GUI half: a CLI failure is logged but
/// doesn't stop the GUI update. If the GUI half can't complete, falls back
/// to opening the release page — same as the old banner-only behaviour —
/// and the dialog stays open on the current (unmodified) install so the user
/// can keep using it.
Future<void> showGuiUpdateDialog(BuildContext context, {required String version, required String url}) {
  return showDialog<void>(
    context: context,
    barrierDismissible: false,
    builder: (BuildContext ctx) => _GuiUpdateDialog(version: version, url: url),
  );
}

enum _UpdatePhase { confirm, working, failed, done }

class _GuiUpdateDialog extends StatefulWidget {
  const _GuiUpdateDialog({required this.version, required this.url});

  final String version;
  final String url;

  @override
  State<_GuiUpdateDialog> createState() => _GuiUpdateDialogState();
}

class _GuiUpdateDialogState extends State<_GuiUpdateDialog> {
  _UpdatePhase _phase = _UpdatePhase.confirm;
  final List<String> _log = <String>[];

  void _say(String s) {
    if (mounted) setState(() => _log.add(s));
  }

  Future<void> _start() async {
    setState(() {
      _phase = _UpdatePhase.working;
      _log.clear();
    });

    _say('Updating the ocforge CLI…');
    final PythonInfo? py = await OcforgeCli.findPython();
    if (py == null) {
      _say('  no Python found on this machine — skipping the CLI update.');
    } else {
      final int code = await OcforgeCli.installOcforge(py, (String l) => _say('  $l'));
      _say(code == 0
          ? '  CLI updated.'
          : '  CLI update failed (exit $code) — continuing with the GUI update anyway.');
    }

    _say('');
    _say('Updating the GUI app…');
    final bool ok = await GuiSelfUpdate.apply(
      tag: 'gui-v${widget.version}',
      log: (String l) => _say('  $l'),
    );
    if (!ok) {
      _say('  could not self-update — opening the release page instead.');
      await openInBrowser(widget.url);
      if (!mounted) return;
      setState(() => _phase = _UpdatePhase.failed);
      return;
    }

    _say('  relaunching…');
    if (!mounted) return;
    setState(() => _phase = _UpdatePhase.done);
    await Future<void>.delayed(const Duration(milliseconds: 400));
    exit(0);
  }

  @override
  Widget build(BuildContext context) {
    final bool closable = _phase == _UpdatePhase.confirm || _phase == _UpdatePhase.failed;
    return AlertDialog(
      title: Text(_phase == _UpdatePhase.confirm
          ? 'Update to ${widget.version}?'
          : 'Updating OCForge'),
      content: SizedBox(
        width: 520,
        child: _phase == _UpdatePhase.confirm
            ? const Text('This updates both the ocforge CLI and this app, then '
                'relaunches. If the automatic swap can\'t complete on this '
                'machine, it falls back to opening the release page instead.')
            : LogConsole(lines: _log, minHeight: 180),
      ),
      actions: <Widget>[
        if (_phase == _UpdatePhase.confirm) ...<Widget>[
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Later')),
          FilledButton(onPressed: _start, child: const Text('Update now')),
        ] else
          TextButton(
            onPressed: closable ? () => Navigator.pop(context) : null,
            child: const Text('Close'),
          ),
      ],
    );
  }
}

class DemoBanner extends StatelessWidget {
  const DemoBanner({super.key});

  @override
  Widget build(BuildContext context) {
    final ColorScheme s = Theme.of(context).colorScheme;
    return Material(
      color: s.tertiaryContainer,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
        child: Row(
          children: <Widget>[
            Icon(Icons.science_outlined, size: 18, color: s.onTertiaryContainer),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                'ocforge CLI not found — running in demo mode with sample data. '
                'Install it with:  pipx install "git+https://github.com/kevinisgoated24-spec/OCforge.git"  '
                '(needs Python 3.11+), then reopen.',
                style: TextStyle(color: s.onTertiaryContainer, fontSize: 12.5),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
