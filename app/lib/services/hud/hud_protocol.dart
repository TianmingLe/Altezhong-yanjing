import 'dart:async';
import 'dart:convert';
import 'dart:developer' as developer;
import 'dart:typed_data';

import 'package:omi_app/services/hud/hud_models.dart';

const int _hudMaxBytes = 64;
const int _hudHeaderBytes = 7;
const int _hudCrcBytes = 2;

int _crc16Ccitt(Uint8List data) {
  var crc = 0xFFFF;
  for (final b in data) {
    crc ^= (b << 8) & 0xFFFF;
    for (var i = 0; i < 8; i++) {
      if ((crc & 0x8000) != 0) {
        crc = ((crc << 1) ^ 0x1021) & 0xFFFF;
      } else {
        crc = (crc << 1) & 0xFFFF;
      }
    }
  }
  return crc & 0xFFFF;
}

void _d(String msg) {
  developer.log(msg, name: 'hud', level: 500);
}

void _w(String msg) {
  developer.log(msg, name: 'hud', level: 900);
}

HudFrame? decodeHudFrame(List<int> rawBytes) {
  if (rawBytes.isEmpty) return null;
  if (rawBytes.length > _hudMaxBytes) {
    _w('hud frame rejected: len>$_hudMaxBytes');
    return null;
  }
  if (rawBytes.length < _hudHeaderBytes + _hudCrcBytes) return null;

  final bytes = Uint8List.fromList(rawBytes);
  final bd = ByteData.sublistView(bytes);

  final typeRaw = bd.getUint8(0);
  final type = HudType.from(typeRaw);
  if (type == null) {
    _w('hud frame rejected: unknown type=$typeRaw');
    return null;
  }

  final priority = bd.getUint8(1);
  final x = bd.getUint16(2, Endian.little);
  final y = bd.getUint16(4, Endian.little);
  final payloadLen = bd.getUint8(6);

  final expectedLen = _hudHeaderBytes + payloadLen + _hudCrcBytes;
  if (expectedLen != bytes.length) {
    _w('hud frame rejected: length mismatch');
    return null;
  }

  final expectedCrc = bd.getUint16(bytes.length - 2, Endian.little);
  final body = bytes.sublist(0, bytes.length - 2);
  final crc = _crc16Ccitt(body);
  if (crc != expectedCrc) {
    _w('hud frame rejected: crc mismatch');
    return null;
  }

  final payload = bytes.sublist(_hudHeaderBytes, _hudHeaderBytes + payloadLen);
  String? text;
  if (type == HudType.text) {
    try {
      text = utf8.decode(payload, allowMalformed: false);
    } catch (_) {
      text = '[?]';
      _w('hud frame: invalid utf8 payload');
    }
  }

  _d('hud frame decoded: type=${type.value} priority=$priority');
  return HudFrame(type: type, priority: priority, x: x, y: y, payload: payload, text: text);
}

class HudProtocol {
  final StreamController<HudFrame> _controller = StreamController<HudFrame>.broadcast();
  Timer? _mockTimer;
  int _mockIndex = 0;

  Stream<HudFrame> get hudStream => _controller.stream;

  void dispose() {
    _mockTimer?.cancel();
    _controller.close();
  }

  HudFrame? parseAndEmit(List<int> blePayload) {
    final frame = decodeHudFrame(blePayload);
    if (frame != null && !_controller.isClosed) _controller.add(frame);
    return frame;
  }

  void enableMockStream(bool enabled) {
    _mockTimer?.cancel();
    if (!enabled) return;

    _mockTimer = Timer.periodic(const Duration(seconds: 2), (_) {
      final type = switch (_mockIndex % 3) {
        0 => HudType.text,
        1 => HudType.toast,
        _ => HudType.alert,
      };
      final priority = switch (type) {
        HudType.alert => 200,
        HudType.toast => 80,
        _ => 50,
      };
      final text = switch (type) {
        HudType.text => 'mock text',
        HudType.toast => 'mock toast',
        HudType.alert => 'mock alert',
        _ => 'mock',
      };
      _mockIndex++;

      if (!_controller.isClosed) {
        _controller.add(
          HudFrame(type: type, priority: priority, x: 320, y: 240, payload: text.codeUnits, text: text),
        );
      }
    });
  }
}

class HudWsAdapter {}

