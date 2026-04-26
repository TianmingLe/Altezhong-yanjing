# Phase 2 BLE 音频流优化（MTU/PHY/Opus/协议）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不引入 >8KB `.dram0.bss` 增量的前提下，将 ESP32‑S3 → 手机的 BLE 音频流升级到 V2 包头（seq+采集时间戳）、固定 MTU=251、优先 2M PHY、Opus 20ms@64kbps CBR，并提供 Unity+Python 可在无硬件环境验证的测试与性能基线。

**Architecture:** 采用混合方案 C：新增 `gatt_mtu_phy`（连接后 MTU/PHY 协商与日志）、`ble_audio_stream`（V2 音频包头/统计/节流），同时最小化改动现有 `app.cpp` 音频主循环与 `opus_encoder`；App 侧通过新增 codec id=22 进行协议版本分流，兼容旧 3B header。

**Tech Stack:** ESP32‑S3 Arduino/PlatformIO（Bluedroid BLE + libopus + RNNoise 已有）、Unity（PlatformIO test）、Python（无硬件吞吐/丢包/延迟模拟）。

---

## 0) 文件结构（锁定边界）

**固件（子模块）**

- Create: `omi/omiGlass/firmware/src/protocols/ble_audio_protocol.h`
- Create: `omi/omiGlass/firmware/src/gatt/gatt_mtu_phy.h`
- Create: `omi/omiGlass/firmware/src/gatt/gatt_mtu_phy.cpp`
- Create: `omi/omiGlass/firmware/src/ble/ble_audio_stream.h`
- Create: `omi/omiGlass/firmware/src/ble/ble_audio_stream.cpp`
- Modify: `omi/omiGlass/firmware/src/config.h`
- Modify: `omi/omiGlass/firmware/src/opus_encoder.h`
- Modify: `omi/omiGlass/firmware/src/opus_encoder.cpp`
- Modify: `omi/omiGlass/firmware/src/app.cpp`
- Create: `omi/omiGlass/firmware/test/test_ble_audio_stream/test_ble_audio_stream.cpp`
- Modify/Create: `omi/omiGlass/firmware/platformio.ini`（增加 test env）

**Python（主仓库）**

- Create: `scripts/test_ble_audio_throughput.py`

**App（子模块：同步协议，非本次实现强制执行，但 plan 给出修改点）**

- Modify: `omi/app/lib/services/devices/omiglass_connection.dart`（识别 codec id 22）
- Modify: `omi/app/lib/services/audio_sources/`（新增/修改 BLE 音频 header 解析为 6B；sync key 改为 6B）

---

## Task 1: 步骤 1 — 分析现有音频链路并写入“基线日志”

**Files:**
- Modify: `omi/omiGlass/firmware/src/app.cpp`

- [ ] **Step 1: 在 `onConnect`（或连接建立时）输出一次基线日志**

在 `ServerHandler::onConnect()` 内（[app.cpp](file:///workspace/omi/omiGlass/firmware/src/app.cpp#L432-L442)）增加日志，字段来自：

- `mtu`: `BLEDevice::getMTU()`
- `phy`: Phase 2 将由 `gatt_mtu_phy` 缓存（先打 `unknown`，Task 3 接上）
- `opus_bitrate`: 新增一个 `opus_get_bitrate()` API（Task 4 提供）

日志格式（严格一致，便于 grep）：

```cpp
ESP_LOGI("BLE_AUDIO", "BLE_AUDIO_BASELINE: mtu=%d, phy=%d, opus_bitrate=%d",
         (int)BLEDevice::getMTU(), (int)gatt_get_phy_mode_or_unknown(), (int)opus_get_bitrate());
```

- [ ] **Step 2: 编译验证（不跑测试）**

Run:

```bash
cd /workspace/omi/omiGlass/firmware
platformio run -e seeed_xiao_esp32s3
```

Expected: `SUCCESS`。

- [ ] **Step 3: Commit（子模块内）**

```bash
cd /workspace/omi
git add omiGlass/firmware/src/app.cpp
git commit -m "chore(ble-audio): add baseline log for mtu/phy/opus bitrate"
```

---

## Task 2: 步骤 2.1 — 固定 MTU=251 + 2M PHY 协商（gatt_mtu_phy）

**Files:**
- Create: `omi/omiGlass/firmware/src/gatt/gatt_mtu_phy.h`
- Create: `omi/omiGlass/firmware/src/gatt/gatt_mtu_phy.cpp`
- Modify: `omi/omiGlass/firmware/src/app.cpp`
- Modify: `omi/omiGlass/firmware/platformio.ini`（如需引入 `CORE_DEBUG_LEVEL`/日志级别一致）

- [ ] **Step 1: 写 failing Unity 测试（仅验证 API 可编译）**

Create:

```cpp
// omi/omiGlass/firmware/test/test_ble_audio_stream/test_ble_audio_stream.cpp
#include <unity.h>

#include "gatt/gatt_mtu_phy.h"

void test_gatt_mtu_phy_api_compiles() {
  gatt_mtu_phy_init();
  TEST_ASSERT_TRUE(gatt_mtu_phy_has_peer_addr() == false || gatt_mtu_phy_has_peer_addr() == true);
}

void setup() {}
void loop() {}

int main(int argc, char **argv) {
  UNITY_BEGIN();
  RUN_TEST(test_gatt_mtu_phy_api_compiles);
  return UNITY_END();
}
```

- [ ] **Step 2: 实现 `gatt_mtu_phy`（最小可用）**

Header 约定：

```cpp
// gatt_mtu_phy.h
#pragma once
#include <stdint.h>

void gatt_mtu_phy_init();
void gatt_mtu_phy_on_connected(const uint8_t peer_bda[6]);
int gatt_mtu_phy_get_mtu();
int gatt_mtu_phy_get_phy_mode_or_unknown(); // 2=2M, 1=1M, 0=unknown
bool gatt_mtu_phy_has_peer_addr();
```

实现要点：

- 在 `gatt_mtu_phy_init()` 中：
  - `BLEDevice::setMTU(251)`；记录返回值，打印 `ESP_LOGI("BLE_GATT", "MTU request=251 result=%d", (int)err);`
  - `BLEDevice::setCustomGattsHandler(...)` 注入 `ESP_GATTS_CONNECT_EVT`，拿到 `remote_bda` 并调用 `gatt_mtu_phy_on_connected()`
- 在 `gatt_mtu_phy_on_connected()` 中：
  - 调用 `esp_ble_gap_set_prefered_phy(peer_bda, ESP_BLE_GAP_PHY_2M_PREF_MASK, ESP_BLE_GAP_PHY_2M_PREF_MASK, ESP_BLE_GAP_PHY_OPTIONS_NONE);`
  - 监听 GAP 回调（`BLEDevice::setCustomGapHandler`）中的 `ESP_GAP_BLE_PHY_UPDATE_COMPLETE_EVT`，记录最终 phy（2M/1M）
  - 统一日志：
    - `ESP_LOGI("BLE_GATT", "BLE_MTU: requested=251 actual=%d", BLEDevice::getMTU());`
    - `ESP_LOGI("BLE_GATT", "BLE_PHY: request=2M result=%d status=%d", phy, status);`

- [ ] **Step 3: 在 `configure_ble()` 调用 init**

在 `configure_ble()` 的 `BLEDevice::init()` 后立即调用：

```cpp
gatt_mtu_phy_init();
```

- [ ] **Step 4: 运行固件单测（只 build）**

新增 test env（编译型）到 `platformio.ini`：

```ini
[env:seeed_xiao_esp32s3_test]
platform = espressif32
board = seeed_xiao_esp32s3
framework = arduino
test_build_project_src = true
test_filter = test_ble_audio_stream
build_flags =
  -DCAMERA_MODEL_XIAO_ESP32S3
  -DCORE_DEBUG_LEVEL=1
  -DBOARD_HAS_PSRAM
  -DCONFIG_BT_BTC_TASK_STACK_SIZE=8192
  -DCONFIG_BTDM_CTRL_HCI_MODE_VHCI=1
lib_deps =
  h2zero/NimBLE-Arduino @ ^1.4.1
  espressif/esp32-camera @ ^2.0.0
  https://github.com/pschatzmann/arduino-libopus.git
  file://lib/rnnoise
```

Run:

```bash
cd /workspace/omi/omiGlass/firmware
platformio test -e seeed_xiao_esp32s3_test --without-uploading --without-testing
```

Expected: build PASS。

- [ ] **Step 5: Commit（子模块内）**

```bash
cd /workspace/omi
git add omiGlass/firmware/src/gatt omiGlass/firmware/src/app.cpp omiGlass/firmware/platformio.ini omiGlass/firmware/test/test_ble_audio_stream/test_ble_audio_stream.cpp
git commit -m "feat(gatt): request MTU=251 and prefer 2M PHY with logs"
```

---

## Task 3: 步骤 2.2 — Opus 参数优化（20ms@64kbps CBR + 电量降级）

**Files:**
- Modify: `omi/omiGlass/firmware/src/config.h`
- Modify: `omi/omiGlass/firmware/src/opus_encoder.cpp`
- Modify: `omi/omiGlass/firmware/src/opus_encoder.h`
- Modify: `omi/omiGlass/firmware/src/app.cpp`（电量降级触发点）

- [ ] **Step 1: 写 failing Unity 测试（Opus 输出上限）**

在 `test_ble_audio_stream.cpp` 增加测试：

```cpp
#include "opus_encoder.h"

void test_opus_config_constants() {
  TEST_ASSERT_EQUAL_INT(64000, opus_get_bitrate());
  TEST_ASSERT_EQUAL_INT(5, opus_get_default_complexity());
  TEST_ASSERT_EQUAL_INT(320, opus_get_frame_samples());
  TEST_ASSERT_TRUE(opus_get_output_max_bytes() <= 160);
}
```

- [ ] **Step 2: 修改 `config.h` 常量**

将（[config.h](file:///workspace/omi/omiGlass/firmware/src/config.h#L146-L159)）更新为：

- `OPUS_BITRATE 64000`
- `OPUS_COMPLEXITY 5`
- `OPUS_VBR 0`
- `OPUS_OUTPUT_MAX_BYTES 160`（已满足）

- [ ] **Step 3: 修改 `opus_encoder_init()` 的 ctl**

在 `opus_encoder.cpp`（[opus_encoder.cpp](file:///workspace/omi/omiGlass/firmware/src/opus_encoder.cpp#L70-L90)）调整：

- `OPUS_SET_VBR(0)`
- `OPUS_SET_PACKET_LOSS_PERC(1)`

并新增 getter API（写在 `opus_encoder.h/cpp`）：

```cpp
int opus_get_bitrate();
int opus_get_default_complexity();
int opus_get_frame_samples();
int opus_get_output_max_bytes();
bool opus_set_complexity(int complexity); // 运行时切换
```

- [ ] **Step 4: 在电量 < 20% 时降级 complexity 并打日志**

触发点放在电量更新逻辑附近（`readBatteryLevel()` 或 `updateBatteryService()` 调用链上，避免每帧判断），伪代码：

```cpp
static bool s_opus_low_battery = false;
if (batteryPercentage < 20 && !s_opus_low_battery) {
  if (opus_set_complexity(3)) {
    ESP_LOGI("BLE_AUDIO", "OPUS_COMPLEXITY downgraded: 5→3 (battery=%d%%)", batteryPercentage);
    s_opus_low_battery = true;
  }
}
if (batteryPercentage >= 25 && s_opus_low_battery) {
  if (opus_set_complexity(5)) {
    ESP_LOGI("BLE_AUDIO", "OPUS_COMPLEXITY upgraded: 3→5 (battery=%d%%)", batteryPercentage);
    s_opus_low_battery = false;
  }
}
```

- [ ] **Step 5: 运行固件单测（build）**

```bash
cd /workspace/omi/omiGlass/firmware
platformio test -e seeed_xiao_esp32s3_test --without-uploading --without-testing
```

Expected: PASS。

- [ ] **Step 6: Commit（子模块内）**

```bash
cd /workspace/omi
git add omiGlass/firmware/src/config.h omiGlass/firmware/src/opus_encoder.* omiGlass/firmware/src/app.cpp omiGlass/firmware/test/test_ble_audio_stream/test_ble_audio_stream.cpp
git commit -m "feat(opus): switch to 64kbps CBR and battery-based complexity downgrade"
```

---

## Task 4: 步骤 2.3 — V2 音频包头（seq+采集 timestamp）与发送模块化

**Files:**
- Create: `omi/omiGlass/firmware/src/protocols/ble_audio_protocol.h`
- Create: `omi/omiGlass/firmware/src/ble/ble_audio_stream.h`
- Create: `omi/omiGlass/firmware/src/ble/ble_audio_stream.cpp`
- Modify: `omi/omiGlass/firmware/src/config.h`（新增 codec id 22）
- Modify: `omi/omiGlass/firmware/src/app.cpp`
- Modify: `omi/omiGlass/firmware/src/opus_encoder.*`（支持“随帧携带 capture_ts”进入回调）

- [ ] **Step 1: 先写 failing Unity 测试（包头编解码 + seq 回绕）**

在 `test_ble_audio_stream.cpp` 加入：

```cpp
#include "protocols/ble_audio_protocol.h"

void test_ble_audio_header_v2_encode_decode() {
  BleAudioHeaderV2 h{.seq = 65535, .timestamp_ms = 123456};
  uint8_t out[BLE_AUDIO_HEADER_V2_SIZE] = {0};
  ble_audio_header_v2_write(out, h);

  BleAudioHeaderV2 r{};
  ble_audio_header_v2_read(out, &r);
  TEST_ASSERT_EQUAL_UINT16(65535, r.seq);
  TEST_ASSERT_EQUAL_UINT32(123456, r.timestamp_ms);

  BleAudioHeaderV2 h2{.seq = (uint16_t)(h.seq + 1), .timestamp_ms = 123460};
  TEST_ASSERT_EQUAL_UINT16(0, h2.seq);
}
```

- [ ] **Step 2: 实现 `protocols/ble_audio_protocol.h`（单一事实来源）**

```cpp
#pragma once
#include <stdint.h>

static constexpr int BLE_AUDIO_HEADER_V2_SIZE = 6;

struct BleAudioHeaderV2 {
  uint16_t seq;
  uint32_t timestamp_ms;
};

inline void ble_audio_header_v2_write(uint8_t* dst, const BleAudioHeaderV2& h) {
  dst[0] = (uint8_t)(h.seq & 0xFF);
  dst[1] = (uint8_t)((h.seq >> 8) & 0xFF);
  dst[2] = (uint8_t)(h.timestamp_ms & 0xFF);
  dst[3] = (uint8_t)((h.timestamp_ms >> 8) & 0xFF);
  dst[4] = (uint8_t)((h.timestamp_ms >> 16) & 0xFF);
  dst[5] = (uint8_t)((h.timestamp_ms >> 24) & 0xFF);
}

inline void ble_audio_header_v2_read(const uint8_t* src, BleAudioHeaderV2* out) {
  out->seq = (uint16_t)(src[0] | (src[1] << 8));
  out->timestamp_ms = (uint32_t)(src[2] | (src[3] << 8) | (src[4] << 16) | (src[5] << 24));
}
```

- [ ] **Step 3: 让 Opus 编码回调携带 capture timestamp（采集时刻）**

改动点：

1) `onMicData()` 捕获 `uint32_t capture_ts_ms = millis();`
2) 将 `capture_ts_ms` 随 PCM 一起送进 Opus pipeline，最终在 encoded callback 中拿到它

最小侵入实现建议：

- 在 `opus_receive_pcm()` 新增一个并行 ring buffer 存储“每个 frame 的 capture_ts”
- 当 `opus_process()` 凑齐一帧 320 samples 时，同时 pop 出对应 timestamp 并回调：

```cpp
typedef void (*opus_encoded_handler_v2)(uint8_t *data, size_t len, uint32_t capture_ts_ms);
void opus_set_callback_v2(opus_encoded_handler_v2 cb);
```

- 兼容：保留旧 `opus_set_callback(opus_encoded_handler)`（内部转发或二选一）

- [ ] **Step 4: 实现 `ble_audio_stream` 负责拼包与 notify**

接口：

```cpp
// ble_audio_stream.h
#pragma once
#include <stdint.h>
#include <stddef.h>
class BLECharacteristic;

void ble_audio_stream_init(BLECharacteristic* audioChar);
void ble_audio_stream_on_encoded_frame(const uint8_t* opus, size_t len, uint32_t capture_ts_ms);
void ble_audio_stream_flush_tx(); // 从 ring buffer 发送（替代 processAudioTx 的发送部分）
uint16_t ble_audio_stream_last_seq();
```

实现要点：

- 包头为 V2：`seq` 从 0 起自增，回绕由 uint16 自然处理
- payload 限制：`len <= 160`，否则丢弃并计数
- 统计：frames_sent / frames_dropped_overflow / tx_bytes_1s
- `notify()` 失败计数（若库不返回状态则只统计调用次数）

- [ ] **Step 5: 改 `app.cpp`：用新模块替换旧 3B header**

- 删除/停用旧的 `audioPacketIndex` / `audio_packet_buffer` 发送逻辑
- `onOpusEncoded()` 改为调用 `ble_audio_stream_on_encoded_frame(...)`
- `processAudioTx()` 改为调用 `ble_audio_stream_flush_tx()`

- [ ] **Step 6: 更新 codec id 为 22**

在 `config.h`：

- `#define AUDIO_CODEC_ID 22`

并确保 `audioCodecCharacteristic` 返回 22（现逻辑已读取 `opus_get_codec_id()`）

- [ ] **Step 7: 运行固件编译 + 单测（build）**

```bash
cd /workspace/omi/omiGlass/firmware
platformio run -e seeed_xiao_esp32s3
platformio test -e seeed_xiao_esp32s3_test --without-uploading --without-testing
```

Expected: SUCCESS + tests build PASS。

- [ ] **Step 8: Commit（子模块内）**

```bash
cd /workspace/omi
git add omiGlass/firmware/src/protocols omiGlass/firmware/src/ble omiGlass/firmware/src/app.cpp omiGlass/firmware/src/config.h omiGlass/firmware/src/opus_encoder.* omiGlass/firmware/test/test_ble_audio_stream/test_ble_audio_stream.cpp
git commit -m "feat(ble-audio): add V2 header with seq+capture timestamp and codec id 22"
```

---

## Task 5: 步骤 2.4 — 节流策略接入（仅限非音频流）与埋点

**Files:**
- Modify: `omi/omiGlass/firmware/src/ble/ble_audio_stream.cpp`
- Modify: `omi/omiGlass/firmware/src/app.cpp`

- [ ] **Step 1: 在 `ble_audio_stream` 增加 1s 滚动带宽统计**

实现：

- 每次 notify 增加 `tx_bytes_1s += payload_len`
- 每 1000ms 将 `tx_bytes_1s` 滚动输出一次 debug log（`ESP_LOGD`），并 reset

日志字段（用于后续延迟/丢包关联）：

- `capture_ts`（最新帧）
- `encode_to_send_ms`（capture_ts 到实际 notify 调用的 delta）

- [ ] **Step 2: app.cpp 侧对照片发送做节流开关**

新增：

```cpp
if (ble_audio_stream_is_congested()) {
  // skip photo notify this loop
} else {
  // existing photo upload logic
}
```

“congested” 判定：`tx_bytes_1s * 8 > 400000`。

- [ ] **Step 3: 编译验证**

```bash
cd /workspace/omi/omiGlass/firmware
platformio run -e seeed_xiao_esp32s3
```

- [ ] **Step 4: Commit（子模块内）**

```bash
cd /workspace/omi
git add omiGlass/firmware/src/ble/ble_audio_stream.cpp omiGlass/firmware/src/app.cpp
git commit -m "feat(ble-audio): add bandwidth stats and photo throttling under congestion"
```

---

## Task 6: 步骤 3.2 — Python 吞吐/丢包/延迟模拟器

**Files:**
- Create: `scripts/test_ble_audio_throughput.py`

- [ ] **Step 1: 写脚本（先实现 selftest + 统计输出）**

脚本行为：

- 输入参数：`--loss-rate`（0-1）、`--frames`、`--frame-ms`（默认 20）、`--bitrate`（默认 64000）、`--payload-max`（默认 160）
- 生成 N 帧“虚拟 BLE 包”（包含 seq+timestamp_ms+payload_len）
- 按 `loss-rate` 随机丢弃帧
- 计算：
  - observed_loss
  - jitter（timestamp 间隔偏差）
  - 端到端延迟模型：`采集(0) + 编码(encode_ms) + 传输(ble_ms) + jitter_buffer(reorder_ms)` 的 p50/p95/p99（默认可用可调的常量模型）
- 输出 markdown 表格到 stdout

实现约束：

- 不依赖第三方库（仅用 stdlib）

- [ ] **Step 2: 运行示例（loss=1%，1000 帧）**

Run:

```bash
cd /workspace
python scripts/test_ble_audio_throughput.py --loss-rate 0.01 --frames 1000
```

Expected: exit 0，打印指标与表格。

- [ ] **Step 3: Commit（主仓库）**

```bash
cd /workspace
git add scripts/test_ble_audio_throughput.py
git commit -m "test(ble): add audio throughput/latency simulator"
git push origin main
```

---

## Task 7: 步骤 4 — 集成验证与内存基线（含 8KB 门禁）

**Files:**
- Modify: 无（仅执行命令与记录结果）

- [ ] **Step 1: 固件 size 输出（Phase 2 对比基线）**

Run:

```bash
cd /workspace/omi/omiGlass/firmware
platformio run -e seeed_xiao_esp32s3 -t size 2>&1 | tee /tmp/phase2_size.log
```

Expected: `SUCCESS`，并记录 `.dram0.bss`。

- [ ] **Step 2: 对比 Phase 2 前基线 `.dram0.bss`**

基线选取：Phase 2 开始前的固件 commit（在子模块上用 `git rev-parse` 记录到 plan 执行日志中）。

Run（示例脚本化做法）：

```bash
cd /workspace/omi
BASE=<phase2_base_commit>
CUR=$(git rev-parse HEAD)
SIZE=~/.platformio/packages/toolchain-xtensa-esp32s3/bin/xtensa-esp32s3-elf-size
ELF=/workspace/omi/omiGlass/firmware/.pio/build/seeed_xiao_esp32s3/firmware.elf
```

分别 build BASE 和 CUR 后对比 `.dram0.bss`，验收：`delta_bss <= 8192`。

- [ ] **Step 3: 固件单测 build**

```bash
cd /workspace/omi/omiGlass/firmware
platformio test -e seeed_xiao_esp32s3_test --without-uploading --without-testing
```

- [ ] **Step 4: Python 模拟测试**

```bash
cd /workspace
python scripts/test_ble_audio_throughput.py --loss-rate 0.01 --frames 1000
```

---

## Task 8: 步骤 5 — 交付物与文档更新

**Files:**
- Modify: `docs/superpowers/specs/2026-04-17-ai-glasses-mvp-design.md`（5.2 节补充 Phase 2 协议与指标）
- Create: `/tmp/phase2_performance.md`（本地生成，可粘贴回 docs）
- Modify: `KNOWN_ISSUES.md`（若仓库存在；否则 Create）

- [ ] **Step 1: 生成性能基线报告（模拟）**

Run:

```bash
cat > /tmp/phase2_performance.md << 'EOF'
# Phase 2 BLE 音频流优化 - 性能基线（模拟）

## 配置
- MTU: 251 (fixed)
- PHY: 2M (preferred), fallback 1M
- Opus: 16kHz/16bit/mono, 20ms(320 samples), 64kbps CBR, complexity=5 (battery<20% => 3)
- Payload: ≤160B
- Packet: [seq(2B)+timestamp_ms(4B)+payload]

## 模拟结果（1000 帧，丢包率 1%）
| 指标 | 目标 | 模拟值 | 状态 |
|------|------|--------|------|
| 丢包恢复率 | ≥99% | <fill by script output> | <pass/fail> |
| 端到端延迟 p95 | ≤150ms | <fill by script output> | <pass/fail> |
| 稳定带宽 | ≥120kbps | <fill by script output> | <pass/fail> |
| RAM 增量 | ≤8KB | <fill by size delta> | <pass/fail> |

## 备注
- 真实硬件验证需连接 ESP32-S3 + 手机 + BLE sniffer
EOF
cat /tmp/phase2_performance.md
```

- [ ] **Step 2: 更新设计总文档 5.2 节（协议与门禁）**

在 `docs/superpowers/specs/2026-04-17-ai-glasses-mvp-design.md` 的固件/协议章节追加：

- codec id 22 的语义
- V2 音频 header（6B）
- timestamp=采集时刻约束
- seq 回绕说明

- [ ] **Step 3: 记录既有 SDK warning 到 KNOWN_ISSUES**

内容包含：

- warning 文本
- 来源：ESP-IDF/SDK config macro redefine（非 Phase 2 引入）
- 决策：MVP 接受

- [ ] **Step 4: 提交与推送（主仓库）**

```bash
cd /workspace
git add docs/superpowers/specs/2026-04-17-ai-glasses-mvp-design.md KNOWN_ISSUES.md
git commit -m "docs: document Phase 2 BLE audio protocol and known warnings"
git push origin main
```

---

## App 同步（执行提醒，不阻塞固件 Phase 2）

Phase 2 若要真实跑通端到端（手机可解码/入 WAL），App 必须同步：

- 识别 codec id 22（`performGetAudioCodec()`）
- BLE 音频 header 从 3B 改为 6B：
  - socket payload strip 6B
  - syncKey 使用 6B（或 `[seq+timestamp]`）

建议把 header 解析统一封装为 `BleAudioPacketV2`（Dart），并在单测覆盖 seq 回绕。

---

## 执行方式（你确认后再开始编码）

Plan complete and saved to `docs/superpowers/plans/2026-04-26-ble-audio-phase2.md`. Two execution options:

1. **Subagent-Driven (recommended)** — 我按 Task 1→8 逐个派发执行单元，阶段性 review，降低回归风险  
2. **Inline Execution** — 在当前会话直接逐条执行并验证

请选择：`1` 或 `2`。

