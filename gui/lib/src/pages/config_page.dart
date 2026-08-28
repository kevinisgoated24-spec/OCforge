// ignore_for_file: use_build_context_synchronously

import 'dart:convert';

import 'package:flutter/material.dart';

import '../controller.dart';
import '../demo.dart';
import '../widgets.dart';
import 'plan_page.dart' show macosChoices, macosLabel;

const Map<String, IconData> _sectionIcon = <String, IconData>{
  'macOS': Icons.apple,
  'SMBIOS': Icons.badge_outlined,
  'boot-args': Icons.terminal_rounded,
  'Booter': Icons.rocket_launch_rounded,
  'Kernel': Icons.memory_rounded,
  'DeviceProperties': Icons.cable_rounded,
  'ACPI': Icons.table_chart_rounded,
  'Kexts': Icons.extension_rounded,
};

class ConfigPage extends StatefulWidget {
  const ConfigPage({super.key});

  @override
  State<ConfigPage> createState() => _ConfigPageState();
}

class _ConfigPageState extends State<ConfigPage> {
  bool _busy = false;
  String? _error;
  List<Map<String, String>> _rows = <Map<String, String>>[];

  Future<void> _explain() async {
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
      String raw;
      if (c.demo) {
        await Future<void>.delayed(const Duration(milliseconds: 450));
        raw = demoExplainJson;
      } else {
        final List<String> args = <String>['explain', '--spec', c.specPath!, '--json'];
        if (c.macosOverride != null) {
          args.addAll(<String>['--macos', '${c.macosOverride}']);
        }
        final r = await c.cli.run(args);
        if (r.exitCode != 0) {
          final String e = '${r.stderr}'.trim();
          throw Exception(e.isEmpty ? 'explain exited ${r.exitCode}' : e);
        }
        raw = '${r.stdout}';
      }
      final List<dynamic> parsed = jsonDecode(raw) as List<dynamic>;
      setState(() {
        _rows = parsed
            .map((dynamic e) => (e as Map<String, dynamic>)
                .map((String k, dynamic v) => MapEntry<String, String>(k, '$v')))
            .toList();
      });
    } catch (e) {
      setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final OcforgeController c = ControllerScope.of(context);

    // preserve section order of first appearance
    final List<String> sections = <String>[];
    for (final Map<String, String> r in _rows) {
      final String s = r['section'] ?? '';
      if (!sections.contains(s)) sections.add(s);
    }

    return PageScroller(
      children: <Widget>[
        FadeInUp(
          child: SectionTitle(
            'Config decisions',
            subtitle:
                'Every hardware-driven edit ocforge makes to config.plist, and why. '
                'Same choices the build writes — this view just explains them.',
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
                    for (final int? choice in macosChoices)
                      ChoiceChip(
                        label: Text(macosLabel(choice)),
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
                label: 'Explain config',
                icon: Icons.rule_rounded,
                busy: _busy,
                onPressed: _busy ? null : _explain,
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
        const SizedBox(height: 24),
        for (int i = 0; i < sections.length; i++) ...<Widget>[
          FadeInUp(
            delay: Duration(milliseconds: 40 * i),
            child: _SectionCard(
              section: sections[i],
              rows: _rows.where((Map<String, String> r) => r['section'] == sections[i]).toList(),
            ),
          ),
          const SizedBox(height: 16),
        ],
      ],
    );
  }
}

class _SectionCard extends StatelessWidget {
  const _SectionCard({required this.section, required this.rows});

  final String section;
  final List<Map<String, String>> rows;

  @override
  Widget build(BuildContext context) {
    final ColorScheme s = Theme.of(context).colorScheme;
    return ExpressiveCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          CardHeader(_sectionIcon[section] ?? Icons.tune_rounded, section),
          const SizedBox(height: 6),
          for (final Map<String, String> r in rows)
            Padding(
              padding: const EdgeInsets.only(top: 14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Wrap(
                    spacing: 10,
                    runSpacing: 6,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: <Widget>[
                      Text(r['setting'] ?? '',
                          style: const TextStyle(
                              fontWeight: FontWeight.w600, fontSize: 13.5)),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                          color: s.secondaryContainer,
                          borderRadius: BorderRadius.circular(999),
                        ),
                        child: Text(r['value'] ?? '',
                            style: TextStyle(
                                fontFamily: 'monospace',
                                fontSize: 12,
                                color: s.onSecondaryContainer)),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(r['reason'] ?? '',
                      style: TextStyle(
                          color: s.onSurfaceVariant, fontSize: 12.5, height: 1.4)),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
