import 'dart:async';
import 'dart:developer' as developer;
import 'dart:ui';

import 'package:flutter/foundation.dart';
import 'package:omi_app/services/hud/hud_models.dart';

class HudOverlayMath {
  static Offset mapPointCover({
    required double sourceWidth,
    required double sourceHeight,
    required double viewWidth,
    required double viewHeight,
    required double x,
    required double y,
  }) {
    final scale = (viewWidth / sourceWidth).clamp(0.0, double.infinity);
    final scale2 = (viewHeight / sourceHeight).clamp(0.0, double.infinity);
    final coverScale = scale > scale2 ? scale : scale2;
    final fittedW = sourceWidth * coverScale;
    final fittedH = sourceHeight * coverScale;
    final offsetX = (fittedW - viewWidth) / 2.0;
    final offsetY = (fittedH - viewHeight) / 2.0;

    final px = (x * coverScale) - offsetX;
    final py = (y * coverScale) - offsetY;

    final cx = px < 0 ? 0.0 : (px > viewWidth ? viewWidth : px);
    final cy = py < 0 ? 0.0 : (py > viewHeight ? viewHeight : py);
    return Offset(cx, cy);
  }
}

class HudOverlayController {
  final ValueNotifier<HudFrame?> active = ValueNotifier<HudFrame?>(null);

  StreamSubscription<HudFrame>? _sub;
  Timer? _dismissTimer;
  Stopwatch? _latency;

  void attach(Stream<HudFrame> stream) {
    detach();
    _sub = stream.listen(_handleFrame);
  }

  void detach() {
    _dismissTimer?.cancel();
    _dismissTimer = null;
    _sub?.cancel();
    _sub = null;
    _latency = null;
    active.value = null;
  }

  void dispose() {
    detach();
    active.dispose();
  }

  void clear() {
    _dismissTimer?.cancel();
    _dismissTimer = null;
    active.value = null;
  }

  void markRendered() {
    final sw = _latency;
    if (sw == null || !sw.isRunning) return;
    sw.stop();
    developer.log('HUD_RENDER_LATENCY_MS=${sw.elapsedMilliseconds}', name: 'hud', level: 500);
  }

  void _handleFrame(HudFrame f) {
    final current = active.value;
    if (current != null && f.priority <= current.priority) return;

    _dismissTimer?.cancel();
    _dismissTimer = null;
    _latency = Stopwatch()..start();
    active.value = f;

    if (f.type == HudType.toast || f.type == HudType.alert) {
      _dismissTimer = Timer(const Duration(milliseconds: 3000), () {
        if (identical(active.value, f)) active.value = null;
      });
    }
  }
}

