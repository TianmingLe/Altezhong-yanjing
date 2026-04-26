## Phase 3：TFLite Micro 边缘视觉特征提取（96×96 Gray → 128D INT8）Design

日期：2026-04-27  
目标固件：ESP32‑S3 Arduino/PlatformIO（[omiGlass/firmware](file:///workspace/omi/omiGlass/firmware)）  
目标 App：Omi Flutter（BLE 设备连接与数据接收在 `omi/app/lib/services/devices/`）

---

### 1. 目标与验收标准

必须全部达标：

1. 输入：96×96 灰度图（或 128×128 降采样到 96×96）
2. 输出：128 维特征向量（INT8，配套量化参数）
3. TFLM 专用 RAM Arena：≤ 30KB（30720 bytes，静态分配，严禁 `malloc/new`）
4. 推理耗时：≤ 20ms / 帧（ESP32‑S3 @ 240MHz，仅特征提取推理部分）
5. 预处理耗时：RGB565 → Gray → 96×96 双线性降采样 ≤ 8ms
6. 精度：与 PC 端参考实现对比的余弦相似度 ≥ 0.85

质量门禁：

- 固件编译：零新增 warning（接受 SDK 既有 warning）
- 单测：Firmware(Unity) + Python 模拟测试通过
- 协议对齐：特征包格式与 App 解析逻辑一致，量化参数具备 model_id 防错

---

### 2. 现状梳理（Phase 2 后基线）

- 固件当前为 Arduino/PlatformIO 工程，尚未集成 TFLite Micro
- 摄像头使用 `esp32-camera`，采集与 JPEG 上传逻辑集中在 [app.cpp](file:///workspace/omi/omiGlass/firmware/src/app.cpp) 中
- BLE 已实现：
  - 音频 V2：`AUDIO_CODEC_ID=22`，payload `[seq(2B)+timestamp_ms(4B)+payload]`
  - 拥塞窗口与节流：`ble_audio_stream_is_congested()`（滚动 1s 带宽窗口 `tx_bytes_1s*8 > 400kbps` 时暂停 JPEG）

Phase 3 将新增“特征提取 + 特征上传”链路，但必须复用既有 BLE 拥塞节流策略（优先保障音频）。

---

### 3. 方案对比（TFLM 集成方式）

#### 3.1 方案 A：Zephyr TFLM 模块

不适用：当前固件工程并非 Zephyr，切换 RTOS/构建系统属于大改，超出 Phase 3 范围。

#### 3.2 方案 B：Vendor TFLM 源码 + 静态 Arena（推荐）

做法：

- 将 `tflite-micro` 以 vendoring 方式纳入固件仓库（仅保留必需 runtime 与 kernels）
- 模型以 `model_data.h`（C 数组）形式存放在 Flash（`const`）
- 推理专用 arena 使用静态数组 `uint8_t arena[30720]` 存放在 `.dram0.bss`
- 通过单测与日志输出确认 arena 用量、推理耗时与输出维度

优点：

- 完全贴合当前 PlatformIO + Arduino 工程
- 内存与 kernels 可控，方便压到 30KB 与 20ms

缺点：

- 需要维护“最小 kernels 列表”与模型版本（model_id）

#### 3.3 方案 C：非深度模型极简特征（查表/手工特征）

不满足约束：与“MobileNetV2 INT8 量化、仅特征层”要求冲突，且相似度门禁风险高。

结论：选择方案 B。

---

### 4. 模型与量化策略

#### 4.1 模型约束

- Backbone：MobileNetV2
- 精度与性能：INT8 PTQ（Post-Training Quantization）
- 输出：128 维 embedding（移除分类 head）

#### 4.2 输出表示（INT8 + 会话级量化参数）

特征输出采用 `int8[128]`，量化参数通过单独 GATT Read 特征按会话同步：

- dequant：`float = scale * (int8 - zero_point)`
- App 侧必须做 L2 归一化后计算余弦相似度

精度门禁：

- `scripts/test_feature_similarity.py` 输出 int8 vs float32 的余弦相似度分布（p50/p95/min），并断言 ≥ 0.85

---

### 5. 协议定义（BLE Feature Streaming）

#### 5.1 新增 Codec ID

- `FEATURE_CODEC_ID = 33`（与音频 `AUDIO_CODEC_ID=22` 区分）

#### 5.2 特征数据包（Notify）

特征 notify payload（小端）：

```
struct BleFeaturePacketV1 {
  uint16_t seq_le;
  uint32_t timestamp_ms_le; // 采集时刻（与音频 timestamp 同源的 millis() 基准）
  int8_t   features[128];
};
```

- 总长度：`2 + 4 + 128 = 134B`
- `seq` 为 uint16，独立计数，回绕 65535→0
- `timestamp_ms` 必须为采集时刻（拿到 camera frame 的时刻），禁止使用发送时刻

#### 5.3 量化参数（会话级协商，Read）

新增 `FEATURE_QUANT_UUID`，特征值载荷（共 6B，小端）：

```
struct FeatureQuantV1 {
  float  scale;      // 4B little-endian float32
  int8_t zero_point; // 1B
  uint8_t model_id;  // 1B
};
```

App 侧策略（强制）：

- 首次连接或发现 `model_id` 变化时，必须重新读取 quant 参数并替换缓存
- 若收到特征包但 quant 未同步或 model_id 不匹配，应拒绝解析并记录日志

---

### 6. 调度与节流策略（与 Phase 2 对齐）

优先级：

- Audio：最高优先级（Phase 2 已实现）
- Feature：低于 Audio，且低于 OTA（若 OTA 进行中）

节流规则：

- 若 `ble_audio_stream_is_congested()==true`（滚动 1s 窗口 `tx_bytes_1s*8 > 400kbps`）：
  - 暂停特征提取与发送（与 JPEG 同级被抑制）
  - 不影响音频

建议频率（默认值，后续可调）：

- 特征发送：5 fps（带宽≈5.56kbps，理论上不构成压力，但必须服从拥塞规则）

---

### 7. 内存与算力预算

#### 7.1 内存预算（硬门禁）

- `tflm_arena`: 30720 bytes（`.dram0.bss`）
- 输入 buffer：96×96 int8 = 9216 bytes（可复用静态 scratch，避免叠加过多 `.bss`）
- 输出：128B
- 协议封包：134B（可用静态临时 buffer）

#### 7.2 性能预算（目标拆解）

- 预处理：RGB565 → Gray → 96×96 双线性 ≤ 8ms
- 推理：TFLM Invoke ≤ 20ms（p95）
- 总计：≤ 28ms（仅作为内部预算；验收以推理 ≤20ms 为硬门禁）

---

### 8. 测试策略

#### 8.1 Firmware(Unity) 单测（无硬件也可 build）

新增 `test/test_feature_extract_tflm/test_feature_extract_tflm.cpp` 覆盖：

- 预处理输出范围：int8 值落在 [-128, 127]
- 推理接口：输入全零/全 255，输出维度=128，不崩溃
- arena 门禁：静态 arena 大小=30720；并输出/校验“实际 arena used”（若 TFLM 运行时可获取）

#### 8.2 Python 模拟测试（无固件可运行）

新增 `scripts/test_feature_similarity.py` 覆盖：

- int8 dequant + L2 norm 正确性
- 与 float32 reference 的 cosine 相似度分布（≥0.85）
- 带宽压力：100 帧特征发送吞吐统计（验证分片/队列策略不会积压）

---

### 9. 交付物清单（Phase 3）

代码：

- `src/vision/feature_extract_tflm.{h,cpp}`：TFLM 推理 + arena 管理
- `src/camera/camera_capture.{h,cpp}`：摄像头抽象 + 预处理（RGB565→96×96 int8）
- `src/protocols/ble_feature_protocol.h`：Feature 协议（header/quant 的单一事实来源）

脚本：

- `scripts/convert_model_to_tflm.py`：模型转换/量化/生成 `model_data.h`
- `scripts/test_feature_similarity.py`：相似度与吞吐模拟测试

文档：

- `docs/superpowers/specs/2026-04-27-phase3-vision-tflm-design.md`（本文）
- 更新 `docs/superpowers/specs/2026-04-17-ai-glasses-mvp-design.md`（补充 Feature 特性与协议）

