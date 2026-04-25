import 'package:flutter/material.dart';
import 'package:omi_app/services/hud/hud_models.dart';
import 'package:omi_app/services/hud/hud_overlay_controller.dart';

class HudOverlayView extends StatefulWidget {
  final Widget child;
  final HudOverlayController controller;

  const HudOverlayView({
    super.key,
    required this.child,
    required this.controller,
  });

  @override
  State<HudOverlayView> createState() => _HudOverlayViewState();
}

class _HudOverlayViewState extends State<HudOverlayView> {
  Key? _activeKey;
  HudFrame? _lastRendered;

  @override
  void dispose() {
    _lastRendered = null;
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      fit: StackFit.expand,
      children: [
        widget.child,
        LayoutBuilder(
          builder: (context, constraints) {
            final w = constraints.maxWidth;
            final h = constraints.maxHeight;
            return ValueListenableBuilder<HudFrame?>(
              valueListenable: widget.controller.active,
              builder: (context, frame, _) {
                _activeKey = frame == null ? null : ValueKey(Object.hash(frame.type, frame.priority, frame.x, frame.y, frame.text));
                if (frame != null && !identical(frame, _lastRendered)) {
                  WidgetsBinding.instance.addPostFrameCallback((_) {
                    if (!mounted) return;
                    if (identical(widget.controller.active.value, frame)) widget.controller.markRendered();
                    _lastRendered = frame;
                  });
                }

                return IgnorePointer(
                  child: AnimatedSwitcher(
                    duration: const Duration(milliseconds: 100),
                    reverseDuration: const Duration(milliseconds: 120),
                    switchInCurve: Curves.easeOut,
                    switchOutCurve: Curves.easeOut,
                    transitionBuilder: (child, animation) {
                      final isIncoming = child.key == _activeKey;
                      final fade = FadeTransition(opacity: animation, child: child);
                      if (!isIncoming) return fade;
                      return SlideTransition(
                        position: Tween<Offset>(begin: const Offset(0, 0.1), end: Offset.zero).animate(animation),
                        child: fade,
                      );
                    },
                    child: frame == null ? const SizedBox.shrink() : _buildOverlay(frame, w, h, _activeKey!),
                  ),
                );
              },
            );
          },
        ),
      ],
    );
  }

  Widget _buildOverlay(HudFrame frame, double w, double h, Key key) {
    if (frame.type == HudType.toast || frame.type == HudType.alert) {
      return Align(
        key: key,
        alignment: Alignment.topCenter,
        child: Padding(
          padding: const EdgeInsets.only(top: 12),
          child: _label(
            text: frame.text ?? '',
            maxWidth: w * 0.8,
            borderColor: frame.type == HudType.alert ? const Color(0xFFFF3D00) : const Color(0xFF00E5FF),
            isAlert: frame.type == HudType.alert,
          ),
        ),
      );
    }

    final p = HudOverlayMath.mapPointCover(
      sourceWidth: 640,
      sourceHeight: 480,
      viewWidth: w,
      viewHeight: h,
      x: frame.x.toDouble(),
      y: frame.y.toDouble(),
    );

    return Positioned(
      key: key,
      left: p.dx,
      top: p.dy,
      child: _label(
        text: frame.text ?? '',
        maxWidth: w * 0.8,
        borderColor: const Color(0xFF00E5FF),
        isAlert: false,
      ),
    );
  }

  Widget _label({
    required String text,
    required double maxWidth,
    required Color borderColor,
    required bool isAlert,
  }) {
    return ConstrainedBox(
      constraints: BoxConstraints(maxWidth: maxWidth),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: const Color(0xFF000000).withValues(alpha: 0.4),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: borderColor.withValues(alpha: isAlert ? 0.85 : 0.65)),
        ),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
          child: Text(
            text,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontSize: 14,
              height: 1.2,
              color: Colors.white,
            ),
          ),
        ),
      ),
    );
  }
}
