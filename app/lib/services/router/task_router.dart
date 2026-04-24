import 'dart:async';


enum ExecuteOn {
  cloud,
  phone,
}


class TaskRouter {
  TaskRouter({
    int networkQuality = 100,
    bool privacyEnabled = false,
  })  : _networkQuality = networkQuality.clamp(0, 100),
        _privacyEnabled = privacyEnabled;

  int _networkQuality;
  bool _privacyEnabled;

  final StreamController<ExecuteOn> _route = StreamController<ExecuteOn>.broadcast();
  ExecuteOn? _last;

  int get networkQuality => _networkQuality;
  bool get privacyEnabled => _privacyEnabled;

  ExecuteOn get executeOn {
    if (_privacyEnabled) return ExecuteOn.phone;
    if (_networkQuality < 20) return ExecuteOn.phone;
    return ExecuteOn.cloud;
  }

  Stream<ExecuteOn> get routeStream => _route.stream;

  void setNetworkQuality(int v) {
    final nv = v.clamp(0, 100);
    if (nv == _networkQuality) return;
    _networkQuality = nv;
    _emit();
  }

  void setPrivacyEnabled(bool enabled) {
    if (enabled == _privacyEnabled) return;
    _privacyEnabled = enabled;
    _emit();
  }

  void _emit() {
    final now = executeOn;
    if (_last == now) return;
    _last = now;
    _route.add(now);
  }

  void dispose() {
    _route.close();
  }
}

