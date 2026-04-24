import 'dart:async';
import 'dart:typed_data';

import 'package:fake_async/fake_async.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:omi_app/services/whisper/whisper_service.dart';

class FakeWorker implements WhisperWorkerApi {
  bool initOk = true;
  bool disposed = false;

  @override
  Future<bool> init(String modelPath) async => initOk;

  @override
  Future<void> dispose() async {
    disposed = true;
  }

  @override
  Future<String> transcribe(Float32List pcm) async => 'ok';
}

class FakeModelManager implements WhisperModelManagerApi {
  @override
  Future<String> ensureModel() async => 'ggml.bin';
}

void main() {
  test('service returns empty string when init fails', () async {
    final w = FakeWorker()..initOk = false;
    final s = WhisperService(
      modelManager: FakeModelManager(),
      worker: w,
    );

    final out = await s.transcribe(Int16List(160));
    expect(out, '');
  });

  test('service disposes worker', () async {
    final w = FakeWorker();
    final s = WhisperService(
      modelManager: FakeModelManager(),
      worker: w,
    );

    await s.transcribe(Int16List(160));
    await s.dispose();
    expect(w.disposed, isTrue);
  });

  test('service keeps 3s ring buffer and can snapshot', () {
    fakeAsync((async) {
      final w = FakeWorker();
      final s = WhisperService(
        modelManager: FakeModelManager(),
        worker: w,
      );

      s.pushPcm(Int16List(48000));
      s.pushPcm(Int16List(16000));
      final snap = s.ringSnapshot();
      expect(snap.length, 48000);
    });
  });
}
