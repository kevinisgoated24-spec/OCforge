// ignore_for_file: use_build_context_synchronously

import 'package:flutter/material.dart';

import '../controller.dart';
import '../demo.dart';
import '../widgets.dart';

const List<int?> _macosChoices = <int?>[null, 26, 15, 14, 13, 12, 11];

String _macosLabel(int? v) => switch (v) {
      null => 'Auto',
      26 => 'Tahoe 26',
      15 => 'Sequoia 15',
      14 => 'Sonoma 14',
      13 => 'Ventura 13',
      12 => 'Monterey 12',
      11 => 'Big Sur 11',
      _ => '$v',
    };

class PlanPage extends StatefulWidget {
  const PlanPage({super.key});

  @override
  State<PlanPage> createState() => _PlanPageState();
}

class _PlanPageState extends State<PlanPage> {
  bool _busy = false;
  String? _error;

  Future<void> _generate() async {
    final OcforgeController c = ControllerScope.of(context);
    if (c.specPath == null) {
      setState(() => _error = 'Detect or open a spec on the Detect tab first.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      if (c.demo) {
        await Future<void>.delayed(const Duration(milliseconds: 500));
        c.setPlan(demoPlanText.trim());
      } else {
        final List<String> args = <String>['plan', '--spec', c.specPath!];
        if (c.macosOverride != null) {
          args.addAll(<String>['--macos', '${c.macosOverride}']);
        }
        final r = await c.cli.run(args);
        final String out = '${r.stdout}'.trim();
        final String err = '${r.stderr}'.trim();
        if (r.exitCode != 0) {
          throw Exception(err.isEmpty ? 'plan exited ${r.exitCode}' : err);
        }
        c.setPlan(out.isEmpty ? err : out);
      }
    } catch (e) {
      setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  List<Widget> _highlights(String text) {
    final List<Widget> chips = <Widget>[];
    for (final String line in text.split('\n')) {
      final String l = line.trim();
      if (l.startsWith('target')) {
        chips.add(SpecChip('target', l.replaceFirst('target', '').trim(),
            icon: Icons.apple));
      } else if (l.startsWith('smbios')) {
        chips.add(SpecChip('SMBIOS', l.replaceFirst('smbios', '').trim(),
            icon: Icons.badge_outlined));
      } else if (l.startsWith('kexts (')) {
        chips.add(SpecChip('kexts', l.substring(7).replaceAll(')', ''),
            icon: Icons.extension_outlined));
      } else if (l.startsWith('SSDTs (')) {
        chips.add(SpecChip('SSDTs', l.substring(7).replaceAll(')', ''),
            icon: Icons.memory_outlined));
      }
    }
    return chips;
  }

  @override
  Widget build(BuildContext context) {
    final OcforgeController c = ControllerScope.of(context);

    return PageScroller(
      children: <Widget>[
        FadeInUp(
          child: SectionTitle(
            'Plan the build',
            subtitle:
                'Pick a macOS target (or let ocforge choose) and preview the kexts, SSDTs and boot-args.',
          ),
        ),
        const SizedBox(height: 22),
        FadeInUp(
          delay: const Duration(milliseconds: 60),
          child: ExpressiveCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                const CardHeader(Icons.apple, 'macOS target'),
                const SizedBox(height: 14),
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: <Widget>[
                    for (final int? choice in _macosChoices)
                      ChoiceChip(
                        label: Text(_macosLabel(choice)),
                        selected: c.macosOverride == choice,
                        onSelected: (_) => c.setMacos(choice),
                      ),
                  ],
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
                label: 'Generate plan',
                icon: Icons.auto_awesome_rounded,
                busy: _busy,
                onPressed: _busy ? null : _generate,
              ),
              const SizedBox(width: 14),
              if (c.specLabel != null)
                Flexible(
                  child: SpecChip('spec', c.specLabel!,
                      icon: Icons.description_outlined),
                ),
            ],
          ),
        ),
        if (_error != null) ...<Widget>[
          const SizedBox(height: 16),
          ExpressiveCard(
            tone: Theme.of(context).colorScheme.errorContainer,
            child: Text(_error!,
                style: TextStyle(
                    color: Theme.of(context).colorScheme.onErrorContainer)),
          ),
        ],
        if (c.planText != null) ...<Widget>[
          const SizedBox(height: 26),
          FadeInUp(
            child: Wrap(
              spacing: 10,
              runSpacing: 10,
              children: _highlights(c.planText!),
            ),
          ),
          const SizedBox(height: 16),
          FadeInUp(
            delay: const Duration(milliseconds: 60),
            child: LogConsole(lines: c.planText!.split('\n'), minHeight: 280),
          ),
        ],
      ],
    );
  }
}
