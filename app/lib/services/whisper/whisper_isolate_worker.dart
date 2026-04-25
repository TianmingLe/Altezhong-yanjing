import 'dart:async';
import 'dart:ffi';
import 'dart:isolate';
import 'dart:typed_data';

import 'package:omi_app/services/whisper/whisper_ffi_native.dart';
import 'package:omi_app/services/whisper/whisper_service.dart';


class WhisperIsolateWorker implements WhisperWorkerApi {
  WhisperIsolateWorker();

  Isolate? _isolate;
  SendPort? _cmd;
  int _seq = 0;

  Future<void> _ensureStarted() async {
    if (_cmd != null) return;
    final ready = ReceivePort();
    _isolate = await Isolate.spawn(_entry, ready.sendPort);
    _cmd = await ready.first as SendPort;
  }

  @override
  Future<bool> init(String modelPath) async {
    await _ensureStarted();
    final resp = ReceivePort();
    _cmd!.send(<String, Object?>{'t': 'init', 'p': modelPath, 'r': resp.sendPort});
    final ok = await resp.first;
    resp.close();
    return ok == true;
  }

  @override
  Future<String> transcribe(Float32List pcm) async {
    await _ensureStarted();
    final resp = ReceivePort();
    final data = TransferableTypedData.fromList(<Uint8List>[pcm.buffer.asUint8List()]);
    _cmd!.send(<String, Object?>{'t': 'tr', 'd': data, 'n': pcm.length, 'r': resp.sendPort, 's': _seq++});
    final out = await resp.first;
    resp.close();
    return out is String ? out : '';
  }

  @override
  Future<void> dispose() async {
    final cmd = _cmd;
    if (cmd != null) {
      final resp = ReceivePort();
      cmd.send(<String, Object?>{'t': 'close', 'r': resp.sendPort});
      await resp.first;
      resp.close();
    }
    _cmd = null;
    _isolate?.kill(priority: Isolate.immediate);
    _isolate = null;
  }
}


void _entry(SendPort ready) {
  final rx = ReceivePort();
  ready.send(rx.sendPort);

  final native = WhisperFfiNative();
  Pointer<Void>? ctx;

  rx.listen((msg) {
    if (msg is! Map) return;
    final type = msg['t'];
    final SendPort? reply = msg['r'] as SendPort?;
    if (reply == null) return;

    try {
      if (type == 'init') {
        final path = msg['p'] as String? ?? '';
        final p = native.init(path);
        if (p.address == 0) {
          reply.send(false);
        } else {
          ctx = p;
          reply.send(true);
        }
        return;
      }

      if (type == 'tr') {
        final c = ctx;
        if (c == null) {
          reply.send('');
          return;
        }
        final ttd = msg['d'] as TransferableTypedData?;
        final n = msg['n'] as int? ?? 0;
        if (ttd == null || n <= 0) {
          reply.send('');
          return;
        }
        final bytes = ttd.materialize().asUint8List();
        final f32 = Float32List.view(bytes.buffer, bytes.offsetInBytes, n);
        final out = native.transcribe(c, f32);
        reply.send(out);
        return;
      }

      if (type == 'close') {
        final c = ctx;
        if (c != null) native.free(c);
        ctx = null;
        reply.send(true);
        rx.close();
        return;
      }
    } catch (_) {
      reply.send(type == 'init' ? false : '');
    }
  });
}
