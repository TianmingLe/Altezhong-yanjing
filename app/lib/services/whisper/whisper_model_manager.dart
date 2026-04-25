import 'dart:convert';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';


class ModelChannel {
  const ModelChannel({
    required this.version,
    required this.fileName,
    required this.sha256,
    required this.url,
  });

  final String version;
  final String fileName;
  final String sha256;
  final String url;
}


abstract class ModelStore {
  Future<bool> exists(String name);
  Future<Uint8List?> read(String name);
  Future<void> write(String name, Uint8List bytes);
  Future<void> delete(String name);
}


abstract class PrefsStore {
  Future<String?> getString(String key);
  Future<void> setString(String key, String value);
}


typedef BytesFetcher = Future<Uint8List> Function(String url);


class WhisperModelManager implements WhisperModelManagerApi {
  WhisperModelManager({
    required this.store,
    required this.prefs,
    required this.fetch,
    required this.channel,
  });

  static const currentKey = 'whisper_model_current_version';
  static const prevKey = 'whisper_model_prev_version';

  final ModelStore store;
  final PrefsStore prefs;
  final BytesFetcher fetch;
  final ModelChannel channel;

  WhisperModelManager copyWith({ModelChannel? channel}) {
    return WhisperModelManager(store: store, prefs: prefs, fetch: fetch, channel: channel ?? this.channel);
  }

  static String sha256Hex(Uint8List bytes) {
    return sha256.convert(bytes).toString();
  }

  @override
  Future<String> ensureModel() async {
    final current = await prefs.getString(currentKey);
    if (current == channel.version && await _isValid(channel.fileName, channel.sha256)) {
      return channel.fileName;
    }

    try {
      final bytes = await fetch(channel.url);
      final digest = sha256Hex(bytes);
      if (digest != channel.sha256) {
        throw StateError('sha mismatch');
      }
      await store.write(channel.fileName, bytes);
      await prefs.setString(prevKey, current ?? '');
      await prefs.setString(currentKey, channel.version);
      return channel.fileName;
    } catch (_) {
      final prev = await prefs.getString(prevKey);
      if (prev != null && prev.isNotEmpty) {
        final prevName = channel.fileName.replaceFirst(channel.version, prev);
        if (await store.exists(prevName)) return prevName;
      }
      return channel.fileName;
    }
  }

  Future<bool> _isValid(String name, String expectedSha) async {
    final bytes = await store.read(name);
    if (bytes == null) return false;
    return sha256Hex(bytes) == expectedSha;
  }
}


abstract class WhisperModelManagerApi {
  Future<String> ensureModel();
}

