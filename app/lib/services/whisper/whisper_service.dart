import 'dart:typed_data';

import 'package:omi_app/services/whisper/pcm_ring_buffer.dart';
import 'package:omi_app/services/whisper/whisper_model_manager.dart';


abstract class WhisperWorkerApi {
  Future<bool> init(String modelPath);
  Future<String> transcribe(Float32List pcm);
  Future<void> dispose();
}


class WhisperService {
  WhisperService({
    required WhisperModelManagerApi modelManager,
    required WhisperWorkerApi worker,
    int sampleRateHz = 16000,
  })  : _modelManager = modelManager,
        _worker = worker,
        _ring = PcmRingBuffer(sampleRateHz: sampleRateHz, seconds: 3);

  final WhisperModelManagerApi _modelManager;
  final WhisperWorkerApi _worker;
  final PcmRingBuffer _ring;

  bool _loading = false;
  bool _ready = false;

  void pushPcm(Int16List pcm) {
    _ring.push(pcm);
  }

  Int16List ringSnapshot() => _ring.snapshot();

  Future<String> transcribe(Int16List pcm) async {
    pushPcm(pcm);

    final ready = await _ensureReady();
    if (!ready) return '';

    final f32 = Float32List(pcm.length);
    for (var i = 0; i < pcm.length; i++) {
      f32[i] = pcm[i] / 32768.0;
    }

    try {
      return await _worker.transcribe(f32);
    } catch (_) {
      return '';
    }
  }

  Future<void> dispose() async {
    try {
      await _worker.dispose();
    } catch (_) {}
  }

  Future<bool> _ensureReady() async {
    if (_ready) return true;
    if (_loading) return false;

    _loading = true;
    try {
      final model = await _modelManager.ensureModel();
      final ok = await _worker.init(model);
      _ready = ok;
      return ok;
    } catch (_) {
      return false;
    } finally {
      _loading = false;
    }
  }
}
