import 'dart:io';
import 'dart:typed_data';

import 'package:http/http.dart' as http;
import 'package:omi_app/services/whisper/whisper_model_manager.dart';
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';


class IoModelStore implements ModelStore {
  IoModelStore(this._dir);

  final Directory _dir;

  File _f(String name) => File('${_dir.path}/$name');

  @override
  Future<bool> exists(String name) async => _f(name).exists();

  @override
  Future<Uint8List?> read(String name) async {
    final f = _f(name);
    if (!await f.exists()) return null;
    return f.readAsBytes();
  }

  @override
  Future<void> write(String name, Uint8List bytes) async {
    final f = _f(name);
    await f.writeAsBytes(bytes, flush: true);
  }

  @override
  Future<void> delete(String name) async {
    final f = _f(name);
    if (await f.exists()) await f.delete();
  }
}


class SharedPrefsStore implements PrefsStore {
  SharedPrefsStore(this._prefs);

  final SharedPreferences _prefs;

  @override
  Future<String?> getString(String key) async => _prefs.getString(key);

  @override
  Future<void> setString(String key, String value) async {
    await _prefs.setString(key, value);
  }
}


Future<WhisperModelManager> createDefaultWhisperModelManager({
  required ModelChannel channel,
  http.Client? client,
}) async {
  final dir = await getApplicationSupportDirectory();
  await dir.create(recursive: true);
  final prefs = await SharedPreferences.getInstance();
  final c = client ?? http.Client();

  return WhisperModelManager(
    store: IoModelStore(dir),
    prefs: SharedPrefsStore(prefs),
    fetch: (url) async {
      final r = await c.get(Uri.parse(url));
      if (r.statusCode != 200) throw StateError('download failed');
      return r.bodyBytes;
    },
    channel: channel,
  );
}

