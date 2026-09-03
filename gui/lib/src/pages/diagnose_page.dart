// ignore_for_file: use_build_context_synchronously

import 'dart:convert';

import 'package:flutter/material.dart';

import '../controller.dart';
import '../demo.dart';
import '../widgets.dart';

/// Scans an OpenCore boot log / macOS panic report for known trouble
/// signatures via `ocforge logcheck --json` — a curated list from
/// Dortania's own troubleshooting guide, not an exhaustive parser.
class DiagnosePage extends StatefulWidget {
  const DiagnosePage({super.key});

  @override
  State<DiagnosePage> createState() => _DiagnosePageState();
}

class _LogFinding {
  const _LogFinding({
    required this.title,
    required this.explanation,
    required this.suggestion,
    required this.lineNo,
    required this.line,
  });

  final String title;
  final String explanation;
  final String suggestion;
  final int lineNo;
  final String line;

  static _LogFinding fromJson(Map<String, dynamic> j) => _LogFinding(
        title: j['title'] as String,
        explanation: j['explanation'] as String,
        suggestion: j['suggestion'] as String,
        lineNo: j['line_no'] as int,
        line: j['line'] as String,
      );
}

class _DiagnosePageState extends State<DiagnosePage> {
  final TextEditingController _path = TextEditingController();
  bool _busy = false;
  bool _checked = false;
  String? _error;
  List<_LogFinding> _findings = <_LogFinding>[];

  @override
  void dispose() {
    _path.dispose();
    super.dispose();
  }

  Future<void> _check() async {
    final OcforgeController c = ControllerScope.of(context);
    final String p = _path.text.trim();
    if (!c.demo && p.isEmpty) {
      setState(() => _error = 'Type the path to a boot log or panic report.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      List<_LogFinding> findings;
      if (c.demo) {
        await Future<void>.delayed(const Duration(milliseconds: 400));
        findings = demoLogcheckFindings.map(_LogFinding.fromJson).toList();
      } else {
        final r = await c.cli.run(<String>['logcheck', '--log', p, '--json']);
        // exit 0 (clean) or 1 (findings) both mean the scan completed fine;
        // anything else (2 = bad path, etc.) is a real failure.
        if (r.exitCode != 0 && r.exitCode != 1) {
          final String e = '${r.stderr}'.trim();
          throw Exception(e.isEmpty ? 'logcheck exited ${r.exitCode}' : e);
        }
        final List<dynamic> raw = jsonDecode('${r.stdout}') as List<dynamic>;
        findings = raw
            .map((dynamic j) => _LogFinding.fromJson(j as Map<String, dynamic>))
            .toList();
      }
      setState(() {
        _findings = findings;
        _checked = true;
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
    final ColorScheme s = Theme.of(context).colorScheme;

    return PageScroller(
      children: <Widget>[
        FadeInUp(
          child: SectionTitle(
            'Diagnose a boot log',
            subtitle: 'Point this at an OpenCore boot log or a macOS panic report and '
                'scan it against a curated list of known trouble signatures from '
                'Dortania\u2019s own troubleshooting guide.',
          ),
        ),
        const SizedBox(height: 20),
        FadeInUp(
          delay: const Duration(milliseconds: 60),
          child: ExpressiveCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                const CardHeader(Icons.troubleshoot_rounded, 'Log file'),
                const SizedBox(height: 12),
                TextField(
                  controller: _path,
                  decoration: InputDecoration(
                    hintText: c.demo
                        ? '(demo mode \u2014 any path works)'
                        : r'e.g. C:\Users\you\Desktop\opencore-2026-01-01-120000.txt',
                    filled: true,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(16),
                      borderSide: BorderSide.none,
                    ),
                  ),
                ),
                const SizedBox(height: 14),
                HeroButton(
                  label: 'Check log',
                  icon: Icons.search_rounded,
                  busy: _busy,
                  onPressed: _busy ? null : _check,
                ),
              ],
            ),
          ),
        ),
        if (_error != null) ...<Widget>[
          const SizedBox(height: 14),
          ExpressiveCard(
            tone: s.errorContainer,
            child: Text(_error!, style: TextStyle(color: s.onErrorContainer)),
          ),
        ],
        if (_checked && _findings.isEmpty && _error == null) ...<Widget>[
          const SizedBox(height: 18),
          FadeInUp(
            child: ExpressiveCard(
              tone: s.secondaryContainer,
              child: Row(
                children: <Widget>[
                  Icon(Icons.check_circle_outline_rounded, color: s.onSecondaryContainer),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      'No known trouble signatures found. This checks a small, curated '
                      'list \u2014 a clean result isn\u2019t proof the boot actually succeeded.',
                      style: TextStyle(color: s.onSecondaryContainer, fontSize: 12.5),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
        for (int i = 0; i < _findings.length; i++) ...<Widget>[
          const SizedBox(height: 14),
          FadeInUp(
            delay: Duration(milliseconds: 60 * i),
            child: _FindingCard(finding: _findings[i]),
          ),
        ],
      ],
    );
  }
}

class _FindingCard extends StatelessWidget {
  const _FindingCard({required this.finding});

  final _LogFinding finding;

  @override
  Widget build(BuildContext context) {
    final ColorScheme s = Theme.of(context).colorScheme;
    return ExpressiveCard(
      tone: s.tertiaryContainer,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Icon(Icons.warning_amber_rounded, color: s.onTertiaryContainer, size: 20),
              const SizedBox(width: 10),
              Expanded(
                child: Text(finding.title,
                    style: TextStyle(
                        color: s.onTertiaryContainer,
                        fontWeight: FontWeight.w700,
                        fontSize: 15)),
              ),
              Text('line ${finding.lineNo}',
                  style: TextStyle(color: s.onTertiaryContainer, fontSize: 11.5)),
            ],
          ),
          const SizedBox(height: 8),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: s.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Text(finding.line,
                style: const TextStyle(fontFamily: 'monospace', fontSize: 12)),
          ),
          const SizedBox(height: 10),
          Text(finding.explanation,
              style: TextStyle(color: s.onTertiaryContainer, fontSize: 12.5)),
          const SizedBox(height: 6),
          Text('Fix: ${finding.suggestion}',
              style: TextStyle(
                  color: s.onTertiaryContainer,
                  fontSize: 12.5,
                  fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}
