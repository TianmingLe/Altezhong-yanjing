import 'dart:ffi';
import 'dart:typed_data';

import 'package:ffi/ffi.dart';


typedef _WhisperInitNative = Pointer<Void> Function(Pointer<Utf8>);
typedef _WhisperInitDart = Pointer<Void> Function(Pointer<Utf8>);

typedef _WhisperFreeNative = Void Function(Pointer<Void>);
typedef _WhisperFreeDart = void Function(Pointer<Void>);

typedef _WhisperTranscribeNative = Int32 Function(
  Pointer<Void>,
  Pointer<Float>,
  Int32,
  Pointer<Uint8>,
  Int32,
);
typedef _WhisperTranscribeDart = int Function(
  Pointer<Void>,
  Pointer<Float>,
  int,
  Pointer<Uint8>,
  int,
);


class WhisperFfiNative {
  WhisperFfiNative({DynamicLibrary? lib}) : _lib = lib ?? DynamicLibrary.open('libwhisper_ffi.so') {
    _init = _lib.lookupFunction<_WhisperInitNative, _WhisperInitDart>('whisper_init');
    _free = _lib.lookupFunction<_WhisperFreeNative, _WhisperFreeDart>('whisper_free');
    _transcribe = _lib.lookupFunction<_WhisperTranscribeNative, _WhisperTranscribeDart>('whisper_transcribe');
  }

  final DynamicLibrary _lib;
  late final _WhisperInitDart _init;
  late final _WhisperFreeDart _free;
  late final _WhisperTranscribeDart _transcribe;

  Pointer<Void> init(String modelPath) {
    final p = modelPath.toNativeUtf8();
    try {
      return _init(p);
    } finally {
      malloc.free(p);
    }
  }

  void free(Pointer<Void> ctx) {
    _free(ctx);
  }

  String transcribe(Pointer<Void> ctx, Float32List pcm, {int outCap = 4096}) {
    final pcmPtr = calloc<Float>(pcm.length);
    for (var i = 0; i < pcm.length; i++) {
      pcmPtr[i] = pcm[i];
    }

    final outPtr = calloc<Uint8>(outCap);
    try {
      final rc = _transcribe(ctx, pcmPtr, pcm.length, outPtr, outCap);
      if (rc < 0) return '';
      final bytes = Uint8List(outCap);
      for (var i = 0; i < outCap; i++) {
        bytes[i] = outPtr[i];
        if (bytes[i] == 0) break;
      }
      final end = bytes.indexWhere((b) => b == 0);
      return String.fromCharCodes(end == -1 ? bytes : bytes.sublist(0, end));
    } finally {
      calloc.free(pcmPtr);
      calloc.free(outPtr);
    }
  }
}

