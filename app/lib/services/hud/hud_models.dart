enum HudType {
  text(0),
  icon(1),
  toast(2),
  alert(3);

  final int value;
  const HudType(this.value);

  static HudType? from(int v) {
    for (final t in HudType.values) {
      if (t.value == v) return t;
    }
    return null;
  }
}

class HudFrame {
  final HudType type;
  final int priority;
  final int x;
  final int y;
  final String? text;
  final List<int> payload;

  const HudFrame({
    required this.type,
    required this.priority,
    required this.x,
    required this.y,
    required this.payload,
    this.text,
  });
}

