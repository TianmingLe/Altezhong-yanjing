import 'dart:async';

import 'package:fake_async/fake_async.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:omi_app/services/hud/hud_models.dart';
import 'package:omi_app/services/hud/hud_overlay_controller.dart';
import 'package:omi_app/services/hud/hud_protocol.dart';

HudFrame _frame(HudType type, int priority, int x, int y, String text) {
  return HudFrame(type: type, priority: priority, x: x, y: y, payload: text.codeUnits, text: text);
}

void main() {
  test('priority overwrite: low -> high replaces', () async {
    final c = HudOverlayController();
    final s = StreamController<HudFrame>.broadcast();
    c.attach(s.stream);

    s.add(_frame(HudType.text, 10, 10, 10, 'low'));
    await Future<void>.delayed(Duration.zero);
    expect(c.active.value?.text, 'low');

    s.add(_frame(HudType.text, 20, 10, 10, 'high'));
    await Future<void>.delayed(Duration.zero);
    expect(c.active.value?.text, 'high');

    c.dispose();
    await s.close();
  });

  test('priority overwrite: high -> low is dropped', () async {
    final c = HudOverlayController();
    final s = StreamController<HudFrame>.broadcast();
    c.attach(s.stream);

    s.add(_frame(HudType.text, 20, 10, 10, 'high'));
    await Future<void>.delayed(Duration.zero);
    expect(c.active.value?.text, 'high');

    s.add(_frame(HudType.text, 10, 10, 10, 'low'));
    await Future<void>.delayed(Duration.zero);
    expect(c.active.value?.text, 'high');

    c.dispose();
    await s.close();
  });

  test('toast auto-dismiss after 3s', () {
    fakeAsync((async) {
      final c = HudOverlayController();
      final s = StreamController<HudFrame>.broadcast();
      c.attach(s.stream);

      s.add(_frame(HudType.toast, 10, 10, 10, 'toast'));
      async.flushMicrotasks();
      expect(c.active.value, isNotNull);

      async.elapse(const Duration(milliseconds: 2999));
      expect(c.active.value, isNotNull);

      async.elapse(const Duration(milliseconds: 1));
      expect(c.active.value, isNull);

      c.dispose();
      s.close();
    });
  });

  test('text does not auto-dismiss', () {
    fakeAsync((async) {
      final c = HudOverlayController();
      final s = StreamController<HudFrame>.broadcast();
      c.attach(s.stream);

      s.add(_frame(HudType.text, 10, 10, 10, 'text'));
      async.flushMicrotasks();
      async.elapse(const Duration(seconds: 10));
      expect(c.active.value, isNotNull);

      c.dispose();
      s.close();
    });
  });

  test('cover mapping clamps to viewport', () {
    final p = HudOverlayMath.mapPointCover(
      sourceWidth: 640,
      sourceHeight: 480,
      viewWidth: 320,
      viewHeight: 320,
      x: 9999,
      y: 9999,
    );
    expect(p.dx, 320);
    expect(p.dy, 320);
  });

  test('attach/detach handles stream recreation', () async {
    final c = HudOverlayController();
    final s1 = StreamController<HudFrame>.broadcast();
    c.attach(s1.stream);
    s1.add(_frame(HudType.text, 10, 10, 10, 'a'));
    await Future<void>.delayed(Duration.zero);
    expect(c.active.value?.text, 'a');
    await s1.close();

    final s2 = StreamController<HudFrame>.broadcast();
    c.attach(s2.stream);
    s2.add(_frame(HudType.text, 20, 10, 10, 'b'));
    await Future<void>.delayed(Duration.zero);
    expect(c.active.value?.text, 'b');

    c.dispose();
    await s2.close();
  });

  test('mock injection drives controller', () {
    fakeAsync((async) {
      final p = HudProtocol();
      final c = HudOverlayController();
      c.attach(p.hudStream);
      p.enableMockStream(true);

      async.elapse(const Duration(milliseconds: 10));
      expect(c.active.value, isNull);

      async.elapse(const Duration(seconds: 2));
      expect(c.active.value, isNotNull);

      p.dispose();
      c.dispose();
    });
  });
}

