import 'dart:typed_data';

class PcmRingBuffer {
  PcmRingBuffer({
    required this.sampleRateHz,
    required this.seconds,
  }) : capacitySamples = sampleRateHz * seconds {
    _buf = Int16List(capacitySamples);
  }

  final int sampleRateHz;
  final int seconds;
  final int capacitySamples;

  late final Int16List _buf;
  int _write = 0;
  int _filled = 0;

  void push(Int16List pcm) {
    if (pcm.isEmpty) return;

    if (pcm.length >= capacitySamples) {
      final tail = pcm.sublist(pcm.length - capacitySamples);
      _buf.setAll(0, tail);
      _write = 0;
      _filled = capacitySamples;
      return;
    }

    for (var i = 0; i < pcm.length; i++) {
      _buf[_write] = pcm[i];
      _write = (_write + 1) % capacitySamples;
    }
    _filled = (_filled + pcm.length).clamp(0, capacitySamples);
  }

  Int16List snapshot() {
    if (_filled == 0) return Int16List(0);
    if (_filled < capacitySamples) return Int16List.fromList(_buf.sublist(0, _filled));

    final out = Int16List(capacitySamples);
    final tailLen = capacitySamples - _write;
    out.setAll(0, _buf.sublist(_write));
    out.setAll(tailLen, _buf.sublist(0, _write));
    return out;
  }
}

