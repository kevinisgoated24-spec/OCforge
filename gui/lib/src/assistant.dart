import 'dart:convert';
import 'dart:io';

/// One backend answer for the in-GUI assistant. Two ways to get one:
///
/// 1. **A local `claude` CLI**, if the user already has Claude Code
///    installed — no API key needed, billed to whatever account they're
///    already signed into. Verified against a real `claude -p` call: it
///    takes the prompt as a plain positional argument, prints the reply to
///    stdout, and exits 0 with empty stderr on success.
/// 2. **The Anthropic API directly**, using a key the user pastes into
///    Settings, for anyone without Claude Code installed.
///
/// Either way this is a single request/response, not a running
/// conversation with tool access — it can't read files, run commands, or
/// touch the build; it only sees whatever text [ask] hands it.
class AiAssistant {
  static const String _model = 'claude-sonnet-5';
  static const String _apiUrl = 'https://api.anthropic.com/v1/messages';

  static const String systemPrimer =
      'You are a terse, practical assistant embedded in the OCForge GUI, a '
      'tool that builds OpenCore EFIs for Hackintosh systems. You are given '
      'the current machine spec and/or plan as context below, if any. Answer '
      'the user\'s question directly. You cannot run commands, read files, or '
      'change anything yourself -- only suggest what the user should do '
      '(a setting to change, a boot-arg, a BIOS option, a kext).';

  /// The first `claude` that answers `--version`, or null if none is on PATH.
  static Future<bool> claudeCliAvailable() async {
    try {
      final ProcessResult r = await Process.run('claude', <String>['--version']);
      return r.exitCode == 0;
    } on ProcessException {
      return false;
    }
  }

  /// Sends [prompt] (with [context] prepended as background, if non-empty)
  /// to whichever backend is available and returns the reply. Throws a
  /// plain [Exception] with a user-facing message on any failure. [useCli]
  /// should come from a fresh [claudeCliAvailable] check (or a cached one no
  /// older than this session) -- if false, [apiKey] must be set.
  static Future<String> ask({
    required String prompt,
    required String context,
    required bool useCli,
    String? apiKey,
  }) async {
    final String full = context.trim().isEmpty
        ? '$systemPrimer\n\n$prompt'
        : '$systemPrimer\n\nContext:\n$context\n\n---\n\nQuestion: $prompt';
    if (useCli) return _askCli(full);
    if (apiKey != null && apiKey.trim().isNotEmpty) return _askApi(apiKey.trim(), full);
    throw Exception('No AI backend available -- install Claude Code, or add an '
        'Anthropic API key in Settings.');
  }

  static Future<String> _askCli(String prompt) async {
    late final ProcessResult r;
    try {
      r = await Process.run('claude', <String>['-p', prompt],
          stdoutEncoding: utf8, stderrEncoding: utf8);
    } on ProcessException catch (e) {
      throw Exception('could not run the claude CLI: $e');
    }
    if (r.exitCode != 0) {
      final String err = '${r.stderr}'.trim();
      throw Exception(err.isEmpty ? 'claude exited ${r.exitCode}' : err);
    }
    final String out = '${r.stdout}'.trim();
    if (out.isEmpty) throw Exception('claude returned no output');
    return out;
  }

  static Future<String> _askApi(String apiKey, String prompt) async {
    final HttpClient client = HttpClient()..connectionTimeout = const Duration(seconds: 25);
    try {
      final HttpClientRequest req = await client.postUrl(Uri.parse(_apiUrl));
      req.headers.set('x-api-key', apiKey);
      req.headers.set('anthropic-version', '2023-06-01');
      req.headers.set(HttpHeaders.contentTypeHeader, 'application/json');
      req.write(jsonEncode(<String, dynamic>{
        'model': _model,
        'max_tokens': 1024,
        'messages': <Map<String, String>>[
          <String, String>{'role': 'user', 'content': prompt},
        ],
      }));
      final HttpClientResponse resp = await req.close();
      final String body = await resp.transform(utf8.decoder).join();
      if (resp.statusCode != 200) {
        throw Exception('Anthropic API error: ${_extractApiError(body) ?? 'HTTP ${resp.statusCode}'}');
      }
      final Map<String, dynamic> json = jsonDecode(body) as Map<String, dynamic>;
      final List<dynamic> content = json['content'] as List<dynamic>? ?? <dynamic>[];
      final StringBuffer sb = StringBuffer();
      for (final dynamic block in content) {
        final Map<String, dynamic> b = block as Map<String, dynamic>;
        if (b['type'] == 'text') sb.write(b['text'] as String? ?? '');
      }
      final String text = sb.toString().trim();
      if (text.isEmpty) throw Exception('empty response from the API');
      return text;
    } on Exception {
      rethrow;
    } on Object catch (e) {
      throw Exception('request failed: $e');
    } finally {
      client.close(force: true);
    }
  }

  static String? _extractApiError(String body) {
    try {
      final Map<String, dynamic> json = jsonDecode(body) as Map<String, dynamic>;
      final Map<String, dynamic>? err = json['error'] as Map<String, dynamic>?;
      return err?['message'] as String?;
    } on Object {
      return null;
    }
  }
}
