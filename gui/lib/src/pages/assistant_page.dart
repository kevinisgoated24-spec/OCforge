import 'dart:convert';

import 'package:flutter/material.dart';

import '../assistant.dart';
import '../controller.dart';
import '../widgets.dart';

class _ChatMessage {
  _ChatMessage(this.fromUser, this.text);
  final bool fromUser;
  final String text;
}

/// A single question/answer helper, not a running agent: each message is
/// one independent request to whichever backend is available (a local
/// Claude Code CLI, else the Anthropic API with a user-supplied key --
/// see assistant.dart). It reads the current Detect/Plan data as context
/// but can't run anything, edit the build, or remember earlier turns
/// beyond what's shown on screen.
class AssistantPage extends StatefulWidget {
  const AssistantPage({super.key});

  @override
  State<AssistantPage> createState() => _AssistantPageState();
}

class _AssistantPageState extends State<AssistantPage> {
  final List<_ChatMessage> _messages = <_ChatMessage>[];
  final TextEditingController _input = TextEditingController();
  final ScrollController _scroll = ScrollController();
  bool _busy = false;
  bool? _cliAvailable; // null = still checking

  @override
  void initState() {
    super.initState();
    AiAssistant.claudeCliAvailable().then((bool v) {
      if (mounted) setState(() => _cliAvailable = v);
    });
  }

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  String _buildContext(OcforgeController c) {
    final StringBuffer b = StringBuffer();
    if (c.machine != null) {
      b.writeln('Machine spec (JSON, from Detect): ${jsonEncode(c.machine)}');
    }
    if (c.planText != null && c.planText!.trim().isNotEmpty) {
      b.writeln('\nLatest plan output:\n${c.planText}');
    }
    return b.toString();
  }

  void _scrollToEnd() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(_scroll.position.maxScrollExtent,
            duration: const Duration(milliseconds: 200), curve: Curves.easeOut);
      }
    });
  }

  Future<void> _send() async {
    final String text = _input.text.trim();
    if (text.isEmpty || _busy || _cliAvailable == null) return;
    final OcforgeController c = ControllerScope.of(context);
    setState(() {
      _messages.add(_ChatMessage(true, text));
      _input.clear();
      _busy = true;
    });
    _scrollToEnd();
    try {
      final String reply = await AiAssistant.ask(
        prompt: text,
        context: _buildContext(c),
        useCli: _cliAvailable!,
        apiKey: c.aiApiKey,
      );
      if (!mounted) return;
      setState(() => _messages.add(_ChatMessage(false, reply)));
    } on Object catch (e) {
      if (!mounted) return;
      setState(() => _messages.add(_ChatMessage(false, 'Error: $e')));
    } finally {
      if (mounted) setState(() => _busy = false);
      _scrollToEnd();
    }
  }

  Future<void> _showApiKeyDialog(OcforgeController c) async {
    final TextEditingController ctrl = TextEditingController(text: c.aiApiKey ?? '');
    final String? result = await showDialog<String>(
      context: context,
      builder: (BuildContext ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
        title: const Text('Anthropic API key'),
        content: SizedBox(
          width: 420,
          child: TextField(
            controller: ctrl,
            obscureText: true,
            autofocus: true,
            decoration: const InputDecoration(
              hintText: 'sk-ant-…',
              border: OutlineInputBorder(),
              helperText: 'Stored locally in prefs.json, in plaintext (this app has no '
                  'OS-keychain integration). Only used when no local Claude Code CLI '
                  'is found.',
              helperMaxLines: 3,
            ),
          ),
        ),
        actions: <Widget>[
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, ctrl.text), child: const Text('Save')),
        ],
      ),
    );
    if (result != null) c.setAiApiKey(result.trim());
  }

  @override
  Widget build(BuildContext context) {
    final OcforgeController c = ControllerScope.of(context);
    final ColorScheme s = Theme.of(context).colorScheme;
    final bool checking = _cliAvailable == null;
    final bool hasKey = c.aiApiKey != null && c.aiApiKey!.isNotEmpty;
    final bool needsKey = !checking && !_cliAvailable! && !hasKey;

    return Padding(
      padding: const EdgeInsets.fromLTRB(28, 28, 28, 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Text('Assistant', style: Theme.of(context).textTheme.headlineMedium),
              const Spacer(),
              if (!checking)
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: Chip(
                    avatar: Icon(_cliAvailable! ? Icons.terminal_rounded : Icons.vpn_key_rounded,
                        size: 16),
                    label: Text(_cliAvailable! ? 'via Claude Code CLI' : 'via API key'),
                    visualDensity: VisualDensity.compact,
                  ),
                ),
              IconButton(
                tooltip: 'Anthropic API key',
                onPressed: checking ? null : () => _showApiKeyDialog(c),
                icon: const Icon(Icons.settings_outlined),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            'Answers using your current Detect/Plan data as context. It\'s a plain '
            'question-and-answer helper — it can\'t run anything, edit your build, '
            'or remember earlier turns beyond what\'s on screen.',
            style: TextStyle(color: s.onSurfaceVariant, fontSize: 12.5),
          ),
          const SizedBox(height: 16),
          if (needsKey)
            Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: ExpressiveCard(
                padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
                child: Row(
                  children: <Widget>[
                    Icon(Icons.info_outline_rounded, color: s.error, size: 20),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        'No Claude Code CLI found on this machine, and no API key set.',
                        style: TextStyle(color: s.onSurfaceVariant, fontSize: 12.5),
                      ),
                    ),
                    TextButton(onPressed: () => _showApiKeyDialog(c), child: const Text('Add key')),
                  ],
                ),
              ),
            ),
          Expanded(
            child: checking
                ? const Center(child: CircularProgressIndicator())
                : _messages.isEmpty
                    ? Center(
                        child: Text(
                          'Ask about your build, an error, a BIOS setting…',
                          style: TextStyle(color: s.onSurfaceVariant),
                        ),
                      )
                    : ListView.builder(
                        controller: _scroll,
                        itemCount: _messages.length,
                        itemBuilder: (BuildContext ctx, int i) => _Bubble(_messages[i]),
                      ),
          ),
          const SizedBox(height: 12),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: <Widget>[
              Expanded(
                child: TextField(
                  controller: _input,
                  minLines: 1,
                  maxLines: 5,
                  enabled: !_busy && !checking,
                  decoration: const InputDecoration(
                    hintText: 'Ask a question…',
                    border: OutlineInputBorder(borderRadius: BorderRadius.all(Radius.circular(16))),
                  ),
                  onSubmitted: (_) => _send(),
                ),
              ),
              const SizedBox(width: 12),
              FilledButton(
                onPressed: (_busy || checking) ? null : _send,
                style: FilledButton.styleFrom(
                    padding: const EdgeInsets.all(16),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16))),
                child: _busy
                    ? const SizedBox(
                        width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.send_rounded),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _Bubble extends StatelessWidget {
  const _Bubble(this.msg);

  final _ChatMessage msg;

  @override
  Widget build(BuildContext context) {
    final ColorScheme s = Theme.of(context).colorScheme;
    final bool me = msg.fromUser;
    return Align(
      alignment: me ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 6),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        constraints: const BoxConstraints(maxWidth: 560),
        decoration: BoxDecoration(
          color: me ? s.primaryContainer : s.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(18),
        ),
        child: SelectableText(
          msg.text,
          style: TextStyle(color: me ? s.onPrimaryContainer : s.onSurface, height: 1.4),
        ),
      ),
    );
  }
}
