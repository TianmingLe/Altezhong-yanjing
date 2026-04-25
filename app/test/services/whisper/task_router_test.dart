import 'package:flutter_test/flutter_test.dart';
import 'package:omi_app/services/router/task_router.dart';

void main() {
  test('task router: privacy forces phone', () {
    final r = TaskRouter(networkQuality: 100, privacyEnabled: true);
    expect(r.executeOn, ExecuteOn.phone);
  });

  test('task router: low network forces phone', () {
    final r = TaskRouter(networkQuality: 19, privacyEnabled: false);
    expect(r.executeOn, ExecuteOn.phone);
  });

  test('task router: default cloud', () {
    final r = TaskRouter(networkQuality: 100, privacyEnabled: false);
    expect(r.executeOn, ExecuteOn.cloud);
  });
}

