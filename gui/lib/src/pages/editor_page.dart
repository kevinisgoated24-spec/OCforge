// ignore_for_file: use_build_context_synchronously

import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../controller.dart';
import '../demo.dart';
import '../widgets.dart';

/// A lightweight OCAT-style config.plist tree editor. Reads/writes via
/// `ocforge plist show|save` (plist <-> JSON with hex `__data__` sentinels) and
/// can run `ocforge validate` against the open file.
class EditorPage extends StatefulWidget {
  const EditorPage({super.key});

  @override
  State<EditorPage> createState() => _EditorPageState();
}

class _EditorPageState extends State<EditorPage> {
  final TextEditingController _path = TextEditingController();
  Object? _root; // decoded JSON: Map / List / primitive
  int _rev = 0; // bumped on load -> forces the tree to rebuild from scratch
  bool _busy = false;
  bool _dirty = false;
  String? _error;

  final List<String> _valLog = <String>[];
  bool _validating = false;
  bool _checkedPendingPath = false;

  @override
  void dispose() {
    _path.dispose();
    super.dispose();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Runs once per instance -- initState() can't reach an InheritedWidget
    // yet, so this is the standard place for "consume something on first
    // build" work. Picks up a config.plist Forge asked to have reviewed
    // here (see OcforgeController.reviewInEditor) and opens it right away.
    if (_checkedPendingPath) return;
    _checkedPendingPath = true;
    final OcforgeController c = ControllerScope.of(context);
    final String? pending = c.pendingEditorPath;
    if (pending != null) {
      c.consumeEditorPath();
      _path.text = pending;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _open();
      });
    }
  }

  void _dirtyMark() {
    if (!_dirty) setState(() => _dirty = true);
  }

  void _snack(String m) => ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
          content: Text(m),
        ),
      );

  Future<void> _open() async {
    final OcforgeController c = ControllerScope.of(context);
    final String p = _path.text.trim();
    if (!c.demo && p.isEmpty) {
      setState(() => _error = 'Type the path to a config.plist.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      String raw;
      if (c.demo) {
        await Future<void>.delayed(const Duration(milliseconds: 400));
        raw = demoConfigJson;
      } else {
        final r = await c.cli.run(<String>['plist', 'show', p]);
        if (r.exitCode != 0) {
          final String e = '${r.stderr}'.trim();
          throw Exception(e.isEmpty ? 'plist show exited ${r.exitCode}' : e);
        }
        raw = '${r.stdout}';
      }
      setState(() {
        _root = jsonDecode(raw) as Object?;
        _rev++;
        _dirty = false;
      });
    } catch (e) {
      setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _save() async {
    final OcforgeController c = ControllerScope.of(context);
    if (_root == null) return;
    if (c.demo) {
      setState(() => _dirty = false);
      _snack('Demo mode — nothing written');
      return;
    }
    final String p = _path.text.trim();
    if (p.isEmpty) {
      _snack('No path to save to');
      return;
    }
    setState(() => _busy = true);
    try {
      final proc = await c.cli.start(<String>['plist', 'save', p]);
      proc.stdin.write(jsonEncode(_root));
      await proc.stdin.close();
      final int code = await proc.exitCode;
      if (code != 0) throw Exception('plist save exited $code');
      setState(() => _dirty = false);
      _snack('Saved $p');
    } catch (e) {
      _snack('$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _validate() async {
    final OcforgeController c = ControllerScope.of(context);
    final String p = _path.text.trim();
    setState(() {
      _validating = true;
      _valLog.clear();
    });
    if (c.demo) {
      for (final String l in demoValidateOutput) {
        if (!mounted) return;
        await Future<void>.delayed(const Duration(milliseconds: 110));
        setState(() => _valLog.add(l));
      }
      setState(() => _validating = false);
      return;
    }
    try {
      final proc = await c.cli.start(<String>['validate', '--config', p]);
      const Utf8Decoder dec = Utf8Decoder(allowMalformed: true);
      void sink(String l) {
        if (mounted) setState(() => _valLog.add(l));
      }

      final StreamSubscription<String> s1 =
          proc.stdout.transform(dec).transform(const LineSplitter()).listen(sink);
      final StreamSubscription<String> s2 =
          proc.stderr.transform(dec).transform(const LineSplitter()).listen(sink);
      final int code = await proc.exitCode;
      await s1.cancel();
      await s2.cancel();
      sink(code == 0 ? '\n\u2713 ocvalidate: clean' : '\n\u2717 ocvalidate exit $code');
    } catch (e) {
      setState(() => _valLog.add('$e'));
    } finally {
      if (mounted) setState(() => _validating = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final OcforgeController c = ControllerScope.of(context);

    return PageScroller(
      children: <Widget>[
        FadeInUp(
          child: SectionTitle(
            'config.plist editor',
            subtitle:
                'Open a config.plist as an editable tree (bools, numbers, strings, hex data), '
                'save it back, and run ocvalidate — all through the ocforge CLI.',
          ),
        ),
        const SizedBox(height: 20),
        FadeInUp(
          delay: const Duration(milliseconds: 60),
          child: ExpressiveCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                const CardHeader(Icons.data_object_rounded, 'File'),
                const SizedBox(height: 12),
                TextField(
                  controller: _path,
                  decoration: InputDecoration(
                    hintText: r'path to config.plist  (e.g. C:\Users\you\Desktop\EFI\OC\config.plist)',
                    filled: true,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(16),
                      borderSide: BorderSide.none,
                    ),
                  ),
                ),
                const SizedBox(height: 14),
                Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: <Widget>[
                    HeroButton(
                      label: c.demo ? 'Load sample' : 'Open',
                      icon: Icons.folder_open_rounded,
                      busy: _busy,
                      onPressed: _busy ? null : _open,
                    ),
                    FilledButton.tonalIcon(
                      onPressed: (_root == null || _busy) ? null : _save,
                      icon: const Icon(Icons.save_rounded),
                      label: Text(_dirty ? 'Save *' : 'Save'),
                    ),
                    OutlinedButton.icon(
                      onPressed: (_root == null || _validating) ? null : _validate,
                      icon: const Icon(Icons.verified_rounded),
                      label: const Text('Validate'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
        if (_error != null) ...<Widget>[
          const SizedBox(height: 14),
          ExpressiveCard(
            tone: Theme.of(context).colorScheme.errorContainer,
            child: Text(_error!,
                style: TextStyle(
                    color: Theme.of(context).colorScheme.onErrorContainer)),
          ),
        ],
        if (_valLog.isNotEmpty) ...<Widget>[
          const SizedBox(height: 16),
          FadeInUp(child: LogConsole(lines: _valLog, minHeight: 140)),
        ],
        if (_root != null) ...<Widget>[
          const SizedBox(height: 22),
          FadeInUp(
            key: ValueKey<int>(_rev),
            child: _TreeNode(
              label: 'config.plist',
              value: _root!,
              path: 'r$_rev',
              onLeafChanged: _dirtyMark,
              top: true,
            ),
          ),
        ],
      ],
    );
  }
}

// --- tree ------------------------------------------------------------------

class _TreeNode extends StatelessWidget {
  const _TreeNode({
    required this.label,
    required this.value,
    required this.path,
    required this.onLeafChanged,
    this.setInParent,
    this.top = false,
  });

  final String label;
  final Object value;
  final String path;
  final VoidCallback onLeafChanged;
  final void Function(Object v)? setInParent;
  final bool top;

  bool get _isData =>
      value is Map && (value as Map).length == 1 && (value as Map).containsKey('__data__');
  bool get _isDate =>
      value is Map && (value as Map).length == 1 && (value as Map).containsKey('__date__');

  @override
  Widget build(BuildContext context) {
    if (_isData) {
      return _leaf(context, _LeafField(
        key: ValueKey<String>('$path#d'),
        initial: (value as Map)['__data__'] as String? ?? '',
        kind: _Kind.hex,
        onCommit: (String v) {
          setInParent?.call(<String, String>{'__data__': v});
          onLeafChanged();
        },
      ));
    }
    if (_isDate) {
      return _leaf(context, _LeafField(
        key: ValueKey<String>('$path#t'),
        initial: (value as Map)['__date__'] as String? ?? '',
        kind: _Kind.text,
        onCommit: (String v) {
          setInParent?.call(<String, String>{'__date__': v});
          onLeafChanged();
        },
      ));
    }

    if (value is Map) {
      final Map<String, dynamic> m = (value as Map).cast<String, dynamic>();
      final List<Widget> kids = <Widget>[
        for (final MapEntry<String, dynamic> e in m.entries)
          _TreeNode(
            label: e.key,
            value: e.value as Object,
            path: '$path/${e.key}',
            onLeafChanged: onLeafChanged,
            setInParent: (Object v) => m[e.key] = v,
          ),
      ];
      return _group(context, '${m.length} keys', kids);
    }

    if (value is List) {
      final List<dynamic> l = value as List<dynamic>;
      final List<Widget> kids = <Widget>[
        for (int i = 0; i < l.length; i++)
          _TreeNode(
            label: '[$i]',
            value: l[i] as Object,
            path: '$path/$i',
            onLeafChanged: onLeafChanged,
            setInParent: (Object v) => l[i] = v,
          ),
      ];
      return _group(context, '${l.length} items', kids);
    }

    if (value is bool) {
      return _leaf(context, Switch(
        value: value as bool,
        onChanged: (bool v) {
          setInParent?.call(v);
          onLeafChanged();
        },
      ));
    }

    final _Kind kind = value is num ? _Kind.number : _Kind.text;
    return _leaf(context, _LeafField(
      key: ValueKey<String>('$path#v'),
      initial: '$value',
      kind: kind,
      onCommit: (String v) {
        setInParent?.call(kind == _Kind.number ? _parseNum(v) : v);
        onLeafChanged();
      },
    ));
  }

  Widget _group(BuildContext context, String badge, List<Widget> kids) {
    final ColorScheme s = Theme.of(context).colorScheme;
    final Widget tile = Theme(
      data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
      child: ExpansionTile(
        initiallyExpanded: top,
        tilePadding: const EdgeInsets.symmetric(horizontal: 4),
        childrenPadding: const EdgeInsets.only(left: 14),
        title: Row(
          children: <Widget>[
            Text(label,
                style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13.5)),
            const SizedBox(width: 10),
            Text(badge, style: TextStyle(color: s.onSurfaceVariant, fontSize: 11.5)),
          ],
        ),
        children: kids,
      ),
    );
    if (!top) return tile;
    return ExpressiveCard(padding: const EdgeInsets.fromLTRB(14, 6, 14, 10), child: tile);
  }

  Widget _leaf(BuildContext context, Widget editor) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        children: <Widget>[
          Expanded(
            flex: 4,
            child: Text(label,
                style: const TextStyle(fontSize: 12.5),
                overflow: TextOverflow.ellipsis),
          ),
          Expanded(flex: 6, child: Align(alignment: Alignment.centerRight, child: editor)),
        ],
      ),
    );
  }
}

Object _parseNum(String v) {
  final String t = v.trim();
  return t.contains('.') ? (double.tryParse(t) ?? 0.0) : (int.tryParse(t) ?? 0);
}

enum _Kind { text, number, hex }

class _LeafField extends StatefulWidget {
  const _LeafField({
    super.key,
    required this.initial,
    required this.kind,
    required this.onCommit,
  });

  final String initial;
  final _Kind kind;
  final ValueChanged<String> onCommit;

  @override
  State<_LeafField> createState() => _LeafFieldState();
}

class _LeafFieldState extends State<_LeafField> {
  late final TextEditingController _c = TextEditingController(text: widget.initial);

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final bool mono = widget.kind == _Kind.hex;
    return TextField(
      controller: _c,
      textAlign: TextAlign.right,
      style: TextStyle(fontSize: 12.5, fontFamily: mono ? 'monospace' : null),
      keyboardType: widget.kind == _Kind.number
          ? const TextInputType.numberWithOptions(signed: true, decimal: true)
          : null,
      inputFormatters: widget.kind == _Kind.hex
          ? <TextInputFormatter>[FilteringTextInputFormatter.allow(RegExp(r'[0-9a-fA-F]'))]
          : null,
      decoration: const InputDecoration(
        isDense: true,
        contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        border: OutlineInputBorder(),
      ),
      onSubmitted: widget.onCommit,
      onTapOutside: (_) {
        FocusManager.instance.primaryFocus?.unfocus();
        widget.onCommit(_c.text);
      },
    );
  }
}
