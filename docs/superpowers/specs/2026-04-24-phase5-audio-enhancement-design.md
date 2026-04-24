## Phase 5：音频增强（RNNoise）+ 手机端离线 ASR（whisper.cpp）Design

### 1. 目标

- 固件侧：在音频上行链路中接入 RNNoise，实现实时降噪（PDM/I2S → 预处理 → Opus → BLE）。
- App 侧：集成 whisper.cpp（Android）并通过触发式路由在“弱网/隐私模式”等条件下启用离线转写，确保体验可用且合规。
- 路由联动：扩展任务路由策略（cloud ↔ phone），并通过 Device Control 特征在必要时通知固件切换采样/编码策略（仅定义接口，具体协议对齐 Phase 3/7 落地）。

### 2. 假设与范围边界

#### 2.1 仓库现状假设

- 当前工作区已落地：
  - Phase 4-i1 后端 Vision API（`/v1/vision/frame` + `/ws/alerts`）
  - Phase 4-i2 App 侧 VisionRouter/FrameUploader/EventSubscriber
- 当前工作区未包含固件仓库与音频采集链路源代码；本设计以“ESP32 类 MCU + Opus + BLE 音频流”为目标形态描述 RNNoise 集成点。

#### 2.2 Phase 5 范围

- 本设计覆盖：
  - RNNoise 固件侧接入点、静态内存分配策略、低电量 bypass、测试策略
  - whisper.cpp Android 集成的模块边界、FFI/Isolate 线程模型、模型管理、触发路由
  - 路由联动契约（不落地具体 BLE 协议实现）
- 不在本阶段强制完成：
  - iOS 端 whisper.cpp
  - 生产级 CI/NDK 矩阵与模型分发 CDN（仅提供接口与建议）

### 3. 质量门禁（Phase 5）

- 固件侧：
  - 禁止动态内存分配（禁止 `malloc/new`）用于 RNNoise 模型态与关键缓冲
  - 峰值 RAM（RNNoise + resample + 预处理 buffer）≤ 40KB（通过静态 buffer 复用实现）
  - 低电量（<20%）自动 bypass 降噪以节省 CPU
- App 侧：
  - whisper 推理必须在后台 Isolate 执行，不得阻塞 UI
  - 模型文件校验（hash/size）与下载失败恢复策略明确
  - 隐私模式开启时默认切到本地 ASR（且可一键关闭本地 ASR）

### 4. 方案选型（2-3 方案）

#### 4.1 RNNoise 集成方案

1) 方案 A（推荐）：Vendor RNNoise + “外部 buffer 初始化”的 wrapper（静态分配）
   - 将 RNNoise 源码以 `lib/rnnoise/` 形式纳入固件工程
   - 增加 `rnnoise_create_inplace(void* buf)` / `rnnoise_destroy_inplace()` 的薄封装，内部不调用 `malloc`
   - 优点：满足“禁止 malloc”，可精确控制内存
   - 缺点：需要对 RNNoise 做轻量 patch 或 wrapper

2) 方案 B：保留 RNNoise 原生 `rnnoise_create()`，通过链接层替换 `malloc` 到静态 arena
   - 优点：改动 RNNoise 更少
   - 缺点：可维护性差且影响面大；不推荐

#### 4.2 whisper.cpp 集成方案（Android）

1) 方案 A（推荐）：NDK 库 + Dart FFI + 后台 Isolate 调度
   - native 提供最小 C ABI：init/load/run/free
   - Dart 层 `dart:ffi` 绑定，并在 Isolate 中执行分段推理
   - 优点：依赖最少、可控、适合“触发式启用”
   - 缺点：需要编译链路与 ABI 兼容策略

2) 方案 B：MethodChannel 调用 Kotlin/Java 封装推理
   - 优点：对 Dart FFI 侵入较小
   - 缺点：长期维护成本更高；不推荐

### 5. RNNoise（固件侧）设计

#### 5.1 音频链路位置（抽象）

```
PDM/I2S capture (PCM int16) → (optional resample) → RNNoise → Opus encode → BLE stream
```

集成点：在“PCM 进入 Opus 编码前”的预处理阶段插入 RNNoise。

#### 5.2 采样率与分帧

- RNNoise 采用 10ms 帧（典型 48k:480 samples）
- 推荐策略：
  1) 若硬件可直接采集 16k：优先 16k 采集，避免 resample
  2) 若必须 48k：在 h1 评估“先降噪再降采样” vs “先降采样再降噪”的 CPU/RAM/效果权衡

#### 5.3 静态内存分配（禁止 malloc）

- 提供 `AudioDenoiserRnnoise` 模块：
  - `static uint8_t g_state[RNNOISE_STATE_BYTES];`
  - `static int16_t g_frame[FRAME_SAMPLES];`（尽可能 in-place 复用）
  - `init()`：in-place 初始化 state
  - `process()`：分帧处理 PCM

#### 5.4 低电量 bypass

- 编译开关：`CONFIG_AUDIO_DENOISE_RNNOISE`
- 运行时：`battery < 20%` → bypass

#### 5.5 单元测试（Unity）

- 稳定性：连续处理 N 秒输入，断言不崩溃、不越界
- 效果 sanity：`clean_sine + white_noise` 输入，近似能量指标验证噪声能量下降（目标 ≥5dB 等价）

### 6. whisper.cpp（App 侧，Android）设计

#### 6.1 目录与构建

- `app/android/app/src/main/cpp/whisper/`：whisper.cpp 源码与 wrapper
- `app/android/app/src/main/cpp/CMakeLists.txt`：构建 `libwhisper_ffi.so`
- 建议锁定 NDK：`25.1.8937393`

#### 6.2 FFI API（最小 C ABI）

- `whisper_init(const char* model_path) -> void* ctx`
- `whisper_free(void* ctx)`
- `whisper_transcribe(void* ctx, const float* pcm_f32, int n, char* out, int out_cap) -> int`

#### 6.3 Isolate 线程模型

- 主 Isolate：路由判断、任务调度、UI stream 输出
- Worker Isolate：模型加载 + 推理
- 触发条件：
  - `privacy_mode=true` → phone
  - `network_quality < 20` → phone
  - 否则 cloud

#### 6.4 模型管理

- 模型：`ggml-tiny.en.bin`（或 multilingual tiny）
- 存储：App documents/cache
- 校验：sha256 或 size+hash；失败删除损坏文件并提示重试

### 7. 路由联动（task_router 扩展）

> 当前工作区未包含 task_router.dart；此处定义策略与接口，落地时映射到实际路由引擎实现。

- `execute_on = cloud | phone`
- 默认 cloud；弱网/隐私 → phone（whisper）
- 状态同步（接口约定）：通过 Device Control 特征通知固件调整采样率/编码参数

### 8. 风险与应对

- RAM 叠加溢出：RNNoise 必须 buffer 复用与分时互斥（与视觉/OTA/TFLM）
- whisper 卡顿：单次音频块 ≤30s，推理期间 UI 展示处理中
- FFI 兼容：锁定 NDK + 最小 CMake + ABI 矩阵（后续）
- 隐私切换：切换期间 3 秒环形缓冲（后续实现）

