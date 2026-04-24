import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:omi_app/services/whisper/pcm_ring_buffer.dart';

void main() {
  test('pcm ring buffer keeps last 3 seconds (48k samples)', () {
    final b = PcmRingBuffer(sampleRateHz: 16000, seconds: 3);
    expect(b.capacitySamples, 48000);

    b.push(Int16List.fromList(List<int>.generate(48000, (i) => i % 1000)));
    final a = b.snapshot();
    expect(a.length, 48000);

    b.push(Int16List.fromList(List<int>.generate(16000, (i) => 2000 + i)));
    final c = b.snapshot();
    expect(c.length, 48000);
    expect(c.first, 2000);
  });
}

