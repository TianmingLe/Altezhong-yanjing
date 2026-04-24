import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:omi_app/services/whisper/whisper_model_manager.dart';

class MemoryStore implements ModelStore {
  final Map<String, Uint8List> files = {};

  @override
  Future<bool> exists(String name) async => files.containsKey(name);

  @override
  Future<Uint8List?> read(String name) async => files[name];

  @override
  Future<void> write(String name, Uint8List bytes) async {
    files[name] = bytes;
  }

  @override
  Future<void> delete(String name) async {
    files.remove(name);
  }
}

class MemoryPrefs implements PrefsStore {
  final Map<String, Object?> m = {};

  @override
  Future<String?> getString(String key) async => m[key] as String?;

  @override
  Future<void> setString(String key, String value) async {
    m[key] = value;
  }
}

void main() {
  test('model manager downloads, verifies sha256, and persists current version', () async {
    final store = MemoryStore();
    final prefs = MemoryPrefs();

    final bytes = Uint8List.fromList(<int>[1, 2, 3]);
    final sha = WhisperModelManager.sha256Hex(bytes);

    final mgr = WhisperModelManager(
      store: store,
      prefs: prefs,
      fetch: (url) async => bytes,
      channel: const ModelChannel(
        version: 'v1',
        fileName: 'ggml-tiny.en.v1.bin',
        sha256: '',
        url: 'https://example.com/m.bin',
      ),
    ).copyWith(channel: ModelChannel(version: 'v1', fileName: 'ggml-tiny.en.v1.bin', sha256: sha, url: 'x'));

    final path = await mgr.ensureModel();
    expect(path, 'ggml-tiny.en.v1.bin');
    expect(await prefs.getString('whisper_model_current_version'), 'v1');
  });

  test('model manager rollbacks to previous version when load fails', () async {
    final store = MemoryStore();
    final prefs = MemoryPrefs();

    final goodBytes = Uint8List.fromList(<int>[1]);
    final goodSha = WhisperModelManager.sha256Hex(goodBytes);

    store.files['ggml-tiny.en.v0.bin'] = goodBytes;
    await prefs.setString('whisper_model_prev_version', 'v0');

    final mgr = WhisperModelManager(
      store: store,
      prefs: prefs,
      fetch: (url) async => Uint8List.fromList(<int>[9]),
      channel: ModelChannel(version: 'v1', fileName: 'ggml-tiny.en.v1.bin', sha256: 'bad', url: 'x'),
    );

    final path = await mgr.ensureModel();
    expect(path, 'ggml-tiny.en.v0.bin');
  });
}

