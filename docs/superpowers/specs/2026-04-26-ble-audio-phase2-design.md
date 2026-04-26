## Phase 2：BLE 音频流优化（MTU/PHY/Opus/协议）Design

日期：2026-04-26  
目标固件：ESP32-S3 Arduino/PlatformIO（[omiGlass/firmware](file:///workspace/omi/omiGlass/firmware)）  
目标 App：Omi Flutter（BLE 连接与音频 WAL 入口在 [OmiGlassConnection](file:///workspace/omi/app/lib/services/devices/omiglass_connection.dart)、[AudioSource](file:///workspace/omi/app/lib/services/audio_sources/audio_source.dart)）

---

### 1. 目标与验收标准（Phase 2）

必须全部达标：

- 音频流丢包率 < 1%（5 分钟连续传输窗口；无硬件时用模拟器替代）
- 端到端延迟 p95 ≤ 150ms（采集→编码→BLE notify→手机接收；无硬件时用模拟器估算并提供埋点）
- 稳定带宽 ≥ 120kbps（Opus 64kbps + 协议开销）
- RAM 增量 ≤ 8KB（仅 Phase 2 相关；以 `.dram0.bss` 对比基线）

质量门禁：

- 固件编译：零新增 warning（接受 ESP-IDF/SDK 既有 `CONFIG_BT_BTC_TASK_STACK_SIZE` 宏重定义 warning）
- 单测：Firmware(Unity) + Python 模拟测试全通过
- 协议对齐：音频分片格式 `[seq(2B) + timestamp_ms(4B) + payload]` 与 App 解析逻辑一致

---

### 2. 现状梳理（代码基线）

#### 2.1 固件音频链路

- 采集：I2S PDM in `mic.cpp`（[mic.cpp](file:///workspace/omi/omiGlass/firmware/src/mic.cpp)）
- 预处理（可选）：48k→16k + RNNoise（[audio_preprocess.cpp](file:///workspace/omi/omiGlass/firmware/src/audio/audio_preprocess.cpp)）在 `onMicData()` 中被调用（[app.cpp](file:///workspace/omi/omiGlass/firmware/src/app.cpp#L325-L338)）
- 编码：`opus_encoder.cpp`（[opus_encoder.cpp](file:///workspace/omi/omiGlass/firmware/src/opus_encoder.cpp)）负责 Opus encode，并通过 callback 将编码结果回传到 `app.cpp:onOpusEncoded()`（[app.cpp](file:///workspace/omi/omiGlass/firmware/src/app.cpp#L340-L369)）
- 发送：`app.cpp:processAudioTx()` 从编码 ring buffer 中取出帧并 `notify()`（[app.cpp](file:///workspace/omi/omiGlass/firmware/src/app.cpp#L390-L427)）

#### 2.2 现有 BLE 音频包格式（Phase 1 基线）

当前固件在 notify payload 前放置 3 字节 header：

- `[packet_index_low(1B) + packet_index_high(1B) + sub_index(1B)]`（`sub_index` 当前恒为 0）
- App 侧将该 3 字节用于 WAL sync key（见 [FrameSyncKey.fromBleHeader](file:///workspace/omi/app/lib/services/audio_sources/audio_source.dart#L21-L24)）

Phase 2 将升级为 6 字节 header（见第 4 章），因此 App 必须同步更新 header 解析与 syncKey 构造。

#### 2.3 MTU/PHY 现状

- 固件当前使用 Arduino-ESP32 BLE（Bluedroid）库（`BLEDevice` / `BLEServer` / `BLECharacteristic`）
- 已确认 BLE 库支持：
  - `BLEDevice::setMTU(uint16_t)` / `BLEDevice::getMTU()`（[BLEDevice.h](file:///root/.platformio/packages/framework-arduinoespressif32/libraries/BLE/src/BLEDevice.h#L31-L66)）
  - 自定义 GAP/GATTS 回调注入：`BLEDevice::setCustomGapHandler` / `BLEDevice::setCustomGattsHandler`（同上）
- 当前固件没有显式设置 MTU、没有 PHY 2M 请求与降级日志

---

### 3. 方案对比（2-3 方案）

#### 3.1 方案 A：最小改动（仅改 app.cpp/config.h/opus_encoder.cpp）

- 优点：改动最少，RAM 增量容易压到 ≤8KB
- 缺点：BLE 音频相关逻辑继续集中在 `app.cpp`，后续扩展（统计、节流、协议演进）维护成本高

#### 3.2 方案 B：全模块化重构（严格创建 src/ble、src/gatt、src/audio、src/scheduler）

- 优点：架构最清晰
- 缺点：改动面大，容易引入回归；不利于控制短周期质量门禁

#### 3.3 方案 C：混合方案（推荐）

新增“关键边界模块”，但不一次性大拆 `app.cpp`：

- `src/ble/ble_audio_stream.{h,cpp}`：音频包头/seq/timestamp、notify、统计、节流策略入口
- `src/gatt/gatt_mtu_phy.{h,cpp}`：MTU/PHY 请求与日志（通过 BLEDevice 自定义回调）
- `src/protocols/ble_audio_protocol.h`：音频 BLE 协议的单一事实来源（固件侧）

---

### 4. 协议定义（Phase 2）

#### 4.1 包头格式（firmware→phone）

音频 notify 的 payload：

```
struct BleAudioPacketV2 {
  uint16_t seq_le;          // LE，uint16，回绕 65535→0
  uint32_t timestamp_ms_le; // LE，采集时刻（capture timestamp）
  uint8_t  opus_payload[N]; // N ≤ 160（20ms @ 64kbps CBR 的经验上限）
}
```

#### 4.2 Timestamp 来源（必须为采集时刻）

- `timestamp_ms` 必须在 `onMicData()` 采样点捕获，而不是“发送时刻”
- 目的：接收端 jitter buffer 需要基于采集时间重排序；发送时间包含编码/调度抖动

实现约束（示意）：

```
uint32_t capture_ts = millis(); // 或 esp_timer_get_time()/1000
```

#### 4.3 Seq 回绕语义

- `seq` 为 uint16，增 1 后回绕
- 接收端丢包判断需处理回绕：

```
if (curr_seq == 0 && last_seq == 65535) => not lost
else if ((uint16_t)(curr_seq - last_seq) > 1) => lost
```

#### 4.4 App 侧兼容性与版本标识

当前 App 以“3 字节 BLE header”构造 `FrameSyncKey`；Phase 2 必须同步升级。

为避免“静默协议破坏”，Phase 2 推荐新增 codec id：

- `AUDIO_CODEC_ID = 22`：Opus 16kHz / 20ms / 64kbps CBR + BleAudioPacketV2（6 字节 header）

App 侧 `performGetAudioCodec()` 需要识别 `22` 并切换到 V2 header 解析（现有映射见 [performGetAudioCodec](file:///workspace/omi/app/lib/services/devices/omiglass_connection.dart#L133-L154)）。

---

### 5. MTU/PHY 设计

#### 5.1 MTU（固定请求 251）

- 目标：请求 MTU=251（BLE 5 常用最大兼容值）
- 实现：在 BLE init 后、开始 advertising 前调用 `BLEDevice::setMTU(251)`，并在连接后记录 `BLEDevice::getMTU()` 作为“实际值”
- 日志：`BLE_AUDIO_BASELINE: mtu=<actual>`

#### 5.2 PHY（优先 2M，失败降级 1M）

- 目标：连接建立后请求 2M PHY；若失败记录原因并继续使用 1M
- 约束：使用 Bluedroid API `esp_ble_gap_set_prefered_phy(peer_addr, ...)`
- 获取 peer addr：通过 `BLEDevice::setCustomGattsHandler()` 拦截 `ESP_GATTS_CONNECT_EVT`，从 `param->connect.remote_bda` 取地址
- 日志：
  - `BLE_PHY: request=2M result=<2M|1M> reason=<...>`
  - `BLE_AUDIO_BASELINE: phy=<1M|2M>`

---

### 6. Opus 参数优化（固件侧）

目标参数：

- 采样：16kHz / int16 / mono
- 帧长：20ms（320 samples）
- 码率：64kbps CBR
- complexity：默认 5，电量 < 20% 自动降级为 3，并记录日志
- 其他：
  - `OPUS_SET_SIGNAL(OPUS_SIGNAL_VOICE)`
  - `OPUS_SET_PACKET_LOSS_PERC(1)`（与丢包目标对齐）
  - `OPUS_SET_VBR(0)`（CBR）

电量降级日志（必须）：

`OPUS_COMPLEXITY downgraded: 5→3 (battery=<n>%)`

---

### 7. 发送节流与统计（固件侧）

#### 7.1 统计（为门禁与调参提供证据）

在 `ble_audio_stream` 内部维护滚动窗口统计：

- `tx_bytes_1s`：1 秒窗口内实际 notify 字节数
- `frames_sent` / `frames_dropped_ring_overflow`：编码 ring buffer 溢出统计
- `notify_failures`：notify 返回错误统计（若 BLE lib 可提供）

#### 7.2 节流策略（仅约束非音频流）

固件侧可控的主要是“照片分片”发送；Phase 2 规则：

- 音频优先级=100：只要连接与订阅存在，必须发送
- 若 `tx_bytes_1s` 折算 > 400kbps：
  - 暂停照片 chunk notify（保持拍照逻辑但不抢占音频带宽）
  - 允许高优 HUD（若后续存在 priority≥200 的 HUD channel）

---

### 8. 测试策略

#### 8.1 固件 Unity 单测（无硬件可编译）

新增测试文件：

- `omiGlass/firmware/test/test_ble_audio_stream/test_ble_audio_stream.cpp`

覆盖：

- Opus 输出包长上限：编码正弦波，断言 `encoded_bytes <= 160`
- 包头编码：seq/timestamp 的 LE 编解码一致
- seq 回绕：65535→0 生成帧后仍可被正确识别为连续
- 节流策略：模拟 `tx_bytes_1s > 400kbps`，断言“音频允许、照片拒绝”

#### 8.2 Python 模拟测试（无固件可运行）

新增脚本：

- `scripts/test_ble_audio_throughput.py`

覆盖：

- 丢包注入（0.5%/1%/2%），统计有效恢复率（jitter buffer 侧）
- 延迟统计：模拟 20ms 采集 + 编码耗时 + 传输 + 解码，输出 p50/p95/p99
- 带宽压力：连续发送 N 帧，统计吞吐与队列积压趋势

---

### 9. 内存增量预算（≤ 8KB）

Phase 2 仅允许新增：

- `ble_audio_stream` 的统计状态与少量 buffer（header 拼装、临时 payload）
- `gatt_mtu_phy` 状态（peer addr、mtu、phy 结果缓存）

必须避免：

- 新增大 ring buffer（现有 `audio_tx_buffer` 已存在）
- 新增额外 Opus 大缓存（由 `opus_encoder` 在 PSRAM 分配；Phase 2 仅改参数）

---

### 10. 已知限制与记录

#### 10.1 固件 warning 门禁

接受 SDK 侧既有 `CONFIG_BT_BTC_TASK_STACK_SIZE` 宏重定义 warning（来自编译 flags 与 ESP-IDF/SDK 配置交互，非 Phase 2 引入）。需要在 `KNOWN_ISSUES.md` 记录，不在 MVP 阶段强制消除。

#### 10.2 HUD 真实联调

沙箱环境无法启动 Flutter App/Android 模拟器，Phase 2 的“真实 4 场景 HUD 联调”在本仓库仅保证：

- `scripts/test_hud_e2e.py --selftest` 通过（协议/优先级/超时逻辑）
- 真实联调需在本地开发环境启动 App 后执行

