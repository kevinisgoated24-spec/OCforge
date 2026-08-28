// ignore_for_file: use_build_context_synchronously

import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';

import '../controller.dart';
import '../demo.dart';
import '../widgets.dart';

class DetectPage extends StatefulWidget {
  const DetectPage({super.key});

  @override
  State<DetectPage> createState() => _DetectPageState();
}

class _DetectPageState extends State<DetectPage> {
  bool _busy = false;
  String? _error;

  Future<void> _detect() async {
    final OcforgeController c = ControllerScope.of(context);
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      if (c.demo) {
        await Future<void>.delayed(const Duration(milliseconds: 550));
        c.setSpec('(demo)', 'sample: Ryzen 5 5600X + RX 6800',
            jsonDecode(demoSpecJson) as Map<String, dynamic>);
      } else {
        final String tmp =
            '${Directory.systemTemp.path}/ocforge_spec_${DateTime.now().millisecondsSinceEpoch}.json';
        final ProcessResult r = await c.cli.run(<String>['probe', '--save', tmp]);
        if (r.exitCode != 0) {
          final String err = '${r.stderr}'.trim();
          throw Exception(err.isEmpty ? 'probe exited ${r.exitCode}' : err);
        }
        final String txt = await File(tmp).readAsString();
        c.setSpec(tmp, 'this PC (detected)', jsonDecode(txt) as Map<String, dynamic>,
            temp: true);
      }
    } catch (e) {
      setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _loadFromFile() async {
    final TextEditingController pathCtl = TextEditingController();
    final String? path = await showDialog<String>(
      context: context,
      builder: (BuildContext ctx) => AlertDialog(
        shape:
            RoundedRectangleBorder(borderRadius: BorderRadius.circular(26)),
        title: const Text('Open a saved spec'),
        content: TextField(
          controller: pathCtl,
          autofocus: true,
          decoration: _dec('Full path to a spec .json'),
          onSubmitted: (String v) => Navigator.pop(ctx, v),
        ),
        actions: <Widget>[
          TextButton(
              onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(
              onPressed: () => Navigator.pop(ctx, pathCtl.text),
              child: const Text('Load')),
        ],
      ),
    );
    if (path == null || path.trim().isEmpty) return;
    final OcforgeController c = ControllerScope.of(context);
    try {
      final File f = File(path.trim());
      final Map<String, dynamic> m =
          jsonDecode(await f.readAsString()) as Map<String, dynamic>;
      c.setSpec(f.path, f.uri.pathSegments.last, m);
      setState(() => _error = null);
    } catch (e) {
      setState(() => _error = 'could not read spec: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    final OcforgeController c = ControllerScope.of(context);
    final Map<String, dynamic>? m = c.machine;

    return PageScroller(
      children: <Widget>[
        FadeInUp(
          child: SectionTitle(
            'Detect your hardware',
            subtitle: c.demo
                ? 'Demo mode — loads a sample machine so you can walk the flow.'
                : 'Runs ocforge probe and reads back the saved spec.',
          ),
        ),
        const SizedBox(height: 24),
        FadeInUp(
          delay: const Duration(milliseconds: 60),
          child: Wrap(
            spacing: 14,
            runSpacing: 14,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: <Widget>[
              HeroButton(
                label: c.demo ? 'Load sample' : 'Detect this PC',
                icon: Icons.memory_rounded,
                busy: _busy,
                onPressed: _busy ? null : _detect,
              ),
              OutlinedButton.icon(
                onPressed: _loadFromFile,
                icon: const Icon(Icons.folder_open_rounded),
                label: const Text('Open spec file'),
              ),
              if (c.specLabel != null)
                SpecChip('spec', c.specLabel!, icon: Icons.description_outlined),
            ],
          ),
        ),
        if (_error != null) ...<Widget>[
          const SizedBox(height: 18),
          _ErrorCard(_error!),
        ],
        const SizedBox(height: 28),
        if (m != null)
          FadeInUp(
            delay: const Duration(milliseconds: 120),
            child: _MachineGrid(m),
          ),
      ],
    );
  }
}

class _MachineGrid extends StatelessWidget {
  const _MachineGrid(this.m);

  final Map<String, dynamic> m;

  @override
  Widget build(BuildContext context) {
    final Map<String, dynamic> cpu =
        (m['cpu'] as Map<String, dynamic>?) ?? <String, dynamic>{};
    final List<dynamic> nets = (m['net'] as List<dynamic>?) ?? <dynamic>[];
    final Map<String, dynamic> storage =
        (m['storage'] as Map<String, dynamic>?) ?? <String, dynamic>{};
    final Map<String, dynamic> fw =
        (m['firmware'] as Map<String, dynamic>?) ?? <String, dynamic>{};
    final Map<String, dynamic>? igpu = m['igpu'] as Map<String, dynamic>?;
    final Map<String, dynamic>? dgpu = m['dgpu'] as Map<String, dynamic>?;
    final Map<String, dynamic> inputs =
        (m['inputs'] as Map<String, dynamic>?) ?? <String, dynamic>{};

    String pci(Map<String, dynamic>? p) {
      if (p == null) return '';
      final String v = '${p['vendor'] ?? ''}';
      final String d = '${p['device'] ?? ''}';
      return (v.isEmpty && d.isEmpty) ? '' : '$v:$d';
    }

    final List<Widget> cards = <Widget>[
      ExpressiveCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            const CardHeader(Icons.developer_board_rounded, 'Processor'),
            const SizedBox(height: 14),
            Text('${cpu['brand'] ?? 'unknown CPU'}',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            Wrap(spacing: 8, runSpacing: 8, children: <Widget>[
              SpecChip('vendor', '${cpu['vendor'] ?? '—'}'),
              if ('${cpu['family'] ?? ''}'.isNotEmpty)
                SpecChip('family', '${cpu['family']}'),
              if ((cpu['intel_gen'] ?? 0) != 0)
                SpecChip('Intel gen', '${cpu['intel_gen']}'),
              SpecChip('cores', '${cpu['cores'] ?? '?'}c / ${cpu['threads'] ?? '?'}t'),
            ]),
          ],
        ),
      ),
      ExpressiveCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            const CardHeader(Icons.videogame_asset_rounded, 'Graphics'),
            const SizedBox(height: 14),
            if (dgpu == null && igpu == null)
              const Text('no GPU reported')
            else ...<Widget>[
              if (dgpu != null)
                _kv(context, 'dGPU',
                    '${dgpu['name'] ?? '?'}   ${pci(dgpu['pci'] as Map<String, dynamic>?)}'),
              if (igpu != null)
                _kv(context, 'iGPU',
                    '${igpu['name'] ?? '?'}   ${pci(igpu['pci'] as Map<String, dynamic>?)}'),
            ],
          ],
        ),
      ),
      ExpressiveCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            const CardHeader(Icons.lan_rounded, 'Network'),
            const SizedBox(height: 14),
            if (nets.isEmpty)
              const Text('no NIC reported')
            else
              ...nets.map((dynamic n) {
                final Map<String, dynamic> nn = n as Map<String, dynamic>;
                final bool wifi = nn['wireless'] == true;
                return _kv(
                  context,
                  wifi ? 'Wi-Fi' : 'Ethernet',
                  '${nn['name'] ?? '?'}   ${pci(nn['pci'] as Map<String, dynamic>?)}',
                );
              }),
          ],
        ),
      ),
      ExpressiveCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            const CardHeader(Icons.dns_rounded, 'Board & storage'),
            const SizedBox(height: 14),
            _kv(context, 'board',
                '${fw['board_vendor'] ?? ''} ${fw['board_name'] ?? ''}'.trim()),
            _kv(context, 'BIOS', '${fw['bios_vendor'] ?? '—'}'),
            _kv(context, 'NVMe', storage['has_nvme'] == true ? 'yes' : 'no'),
            _kv(context, 'chassis', '${m['chassis'] ?? '—'}'),
            if (inputs['has_touchpad'] == true)
              _kv(context, 'touchpad', '${inputs['touchpad_bus'] ?? 'yes'}'),
          ],
        ),
      ),
    ];

    return LayoutBuilder(
      builder: (BuildContext context, BoxConstraints bc) {
        final int cols = bc.maxWidth > 900 ? 2 : 1;
        final double w =
            cols == 2 ? (bc.maxWidth - 18) / 2 : bc.maxWidth;
        return Wrap(
          spacing: 18,
          runSpacing: 18,
          children: <Widget>[
            for (final Widget card in cards)
              SizedBox(width: w, child: card),
          ],
        );
      },
    );
  }

  Widget _kv(BuildContext context, String k, String v) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          SizedBox(
            width: 78,
            child: Text(k,
                style: TextStyle(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                    fontSize: 12.5)),
          ),
          Expanded(
              child: Text(v, style: const TextStyle(fontWeight: FontWeight.w500))),
        ],
      ),
    );
  }
}

class _ErrorCard extends StatelessWidget {
  const _ErrorCard(this.message);

  final String message;

  @override
  Widget build(BuildContext context) {
    final ColorScheme s = Theme.of(context).colorScheme;
    return ExpressiveCard(
      tone: s.errorContainer,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Icon(Icons.error_outline_rounded, color: s.onErrorContainer),
          const SizedBox(width: 12),
          Expanded(
            child: Text(message,
                style: TextStyle(color: s.onErrorContainer, height: 1.4)),
          ),
        ],
      ),
    );
  }
}

InputDecoration _dec(String hint) => InputDecoration(
      hintText: hint,
      filled: true,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: BorderSide.none,
      ),
    );
