## g4) App HUD 叠加渲染（MVP）

- 渲染结构
  - `HudOverlayView(child, controller)` 使用 `Stack` 叠加 HUD，仅 HUD 层通过 `ValueListenableBuilder` 重建
  - 相机预览层不使用 `setState` 包裹，避免 CameraPreview 重绘
- 优先级与消退
  - `new.priority > current.priority` 覆盖，否则丢弃
  - `toast/alert` 3000ms 自动清空，`text/icon` 保持直到被覆盖或手动清除
- 坐标映射
  - 固件坐标基准 640×480，原点左上角
  - 按 `BoxFit.cover` 计算 scale 与裁剪偏移（crop offset），映射到预览渲染尺寸后对坐标 clamp，避免越界导致 RenderBox 崩溃
- 动效与 UI Token
  - 入场：Slide(Y=0.1h, 100ms)，退场：Opacity(120ms)
  - 主色 `#00E5FF`，告警 `#FF3D00`，遮罩 `#000000` @ 0.4，字体 14sp / 行高 1.2 / 最大宽度 80vw / 省略号
- 延迟测量（p95 ≤150ms 目标）
  - controller 在接收帧时启动 `Stopwatch`
  - view 在帧首次呈现后通过 post-frame 回调调用 `markRendered()` 输出 `HUD_RENDER_LATENCY_MS`
- 内存约束
  - 叠加层仅持有 `HudFrame` 与定时器/订阅引用，不持有相机流；额外内存主要来自 widget 树与少量对象，目标 ≤5MB

