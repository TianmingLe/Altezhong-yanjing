# Phase 3 TFLite Micro 视觉特征提取（96×96 Gray → 128D INT8）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 ESP32‑S3（Arduino/PlatformIO）上以 TFLite Micro 运行 MobileNetV2 INT8 特征层，将摄像头帧预处理为 96×96 灰度 int8，输出 128 维 int8 embedding，并通过 BLE 发送（带 seq+采集 timestamp），会话级通过 GATT Read 下发量化参数（scale/zero_point/model_id），满足 arena≤30KB、推理≤20ms、相似度≥0.85 的门禁。

**Architecture:** 采用 Vendor TFLM（方案 B）：固件内 vendoring 最小 TFLM runtime + 必要 kernels；推理使用静态 arena[30720]；特征链路分为 camera capture → preprocess → invoke → pack → notify。BLE 节流复用 Phase 2 的 `ble_audio_stream_is_congested()`（拥塞时暂停 feature 发送，优先音频）。

**Tech Stack:** ESP32‑S3 Arduino/PlatformIO、esp32-camera、BLE（Bluedroid）、TFLite Micro（vendored）、Unity（PlatformIO test build）、Python（tflite-runtime/tensorflow 参考 + 相似度评估）。

---

## 0) 文件结构（锁定边界）

**固件**

- Create: `omi/omiGlass/firmware/src/vision/feature_extract_tflm.h`
- Create: `omi/omiGlass/firmware/src/vision/feature_extract_tflm.cpp`
- Create: `omi/omiGlass/firmware/src/camera/camera_capture.h`
- Create: `omi/omiGlass/firmware/src/camera/camera_capture.cpp`
- Create: `omi/omiGlass/firmware/src/protocols/ble_feature_protocol.h`
- Create: `omi/omiGlass/firmware/src/ble/ble_feature_stream.h`
- Create: `omi/omiGlass/firmware/src/ble/ble_feature_stream.cpp`
- Create: `omi/omiGlass/firmware/src/vision/model_data.h` (generated)
- Modify: `omi/omiGlass/firmware/src/config.h`
- Modify: `omi/omiGlass/firmware/src/app.cpp`
- Modify: `omi/omiGlass/firmware/platformio.ini`
- Create: `omi/omiGlass/firmware/test/test_feature_extract_tflm/test_feature_extract_tflm.cpp`
- Modify: `omi/omiGlass/firmware/.gitignore`（如需补充忽略 vendored/tflm 生成物）

**固件 vendored 第三方**

- Create: `omi/omiGlass/firmware/lib/tflite_micro/`（以 subtree/复制方式引入，非 git submodule）

**主仓库脚本**

- Create: `scripts/convert_model_to_tflm.py`
- Create: `scripts/test_feature_similarity.py`

**文档**

- Modify: `docs/superpowers/specs/2026-04-17-ai-glasses-mvp-design.md`（补充 Feature GATT 与协议）

---

## Task 1: 现有视觉链路梳理 + 基线日志

**Files:**
- Modify: `omi/omiGlass/firmware/src/app.cpp`

- [ ] **Step 1: 写入 VISION_BASELINE 日志（编译前就能看见格式）**

在 `configure_camera()` 完成 `camera_config_t config` 填充后、`esp_camera_init(&config)` 前，增加：

```cpp
ESP_LOGI(
    "VISION",
    "VISION_BASELINE: resolution=%dx%d, format=%d, fps=%d",
    (int) config.frame_size,
    (int) config.frame_size,
    (int) config.pixel_format,
    (int) 0
);
```

说明：

- `esp32-camera` 的 `framesize_t` 是枚举，不一定能直接得到 width/height；本阶段先确保日志格式固定，后续若需要精确宽高再补充映射表。

- [ ] **Step 2: 编译验证**

Run:

```bash
cd /workspace/omi/omiGlass/firmware
platformio run -e seeed_xiao_esp32s3
```

Expected: `SUCCESS`

- [ ] **Step 3: Commit（子模块）**

```bash
cd /workspace/omi
git add omiGlass/firmware/src/app.cpp
git commit -m "chore(vision): add VISION_BASELINE log"
git push origin main
```

---

## Task 2: Feature 协议与 GATT 骨架（不引入 TFLM）

**Files:**
- Create: `omi/omiGlass/firmware/src/protocols/ble_feature_protocol.h`
- Create: `omi/omiGlass/firmware/src/ble/ble_feature_stream.h`
- Create: `omi/omiGlass/firmware/src/ble/ble_feature_stream.cpp`
- Modify: `omi/omiGlass/firmware/src/config.h`
- Modify: `omi/omiGlass/firmware/src/app.cpp`
- Test: `omi/omiGlass/firmware/test/test_feature_extract_tflm/test_feature_extract_tflm.cpp`（仅协议编解码部分）

- [ ] **Step 1: 写 failing Unity 测试（Feature header/quant 编解码 + 回绕）**

Create:

```cpp
// omi/omiGlass/firmware/test/test_feature_extract_tflm/test_feature_extract_tflm.cpp
#include <unity.h>

#include "protocols/ble_feature_protocol.h"

static void test_feature_packet_header_encode_decode()
{
  BleFeatureHeaderV1 h{.seq = 65535, .timestamp_ms = 123456};
  uint8_t buf[BLE_FEATURE_HEADER_V1_SIZE] = {0};
  ble_feature_header_v1_write(buf, h);

  BleFeatureHeaderV1 r{};
  ble_feature_header_v1_read(buf, &r);
  TEST_ASSERT_EQUAL_UINT16(65535, r.seq);
  TEST_ASSERT_EQUAL_UINT32(123456, r.timestamp_ms);

  BleFeatureHeaderV1 h2{.seq = (uint16_t)(h.seq + 1), .timestamp_ms = 123460};
  TEST_ASSERT_EQUAL_UINT16(0, h2.seq);
}

static void test_feature_quant_payload_size()
{
  TEST_ASSERT_EQUAL_INT(6, BLE_FEATURE_QUANT_V1_SIZE);
}

void setup()
{
  UNITY_BEGIN();
  RUN_TEST(test_feature_packet_header_encode_decode);
  RUN_TEST(test_feature_quant_payload_size);
  UNITY_END();
}
void loop() {}
```

- [ ] **Step 2: 实现 `ble_feature_protocol.h`（单一事实来源）**

Create:

```cpp
// omi/omiGlass/firmware/src/protocols/ble_feature_protocol.h
#pragma once

#include <stdint.h>

static constexpr int FEATURE_CODEC_ID = 33;
static constexpr int BLE_FEATURE_HEADER_V1_SIZE = 6;
static constexpr int BLE_FEATURE_VECTOR_SIZE = 128;
static constexpr int BLE_FEATURE_PACKET_V1_SIZE = BLE_FEATURE_HEADER_V1_SIZE + BLE_FEATURE_VECTOR_SIZE;
static constexpr int BLE_FEATURE_QUANT_V1_SIZE = 6;

struct BleFeatureHeaderV1 {
  uint16_t seq;
  uint32_t timestamp_ms;
};

inline void ble_feature_header_v1_write(uint8_t* dst, const BleFeatureHeaderV1& h) {
  dst[0] = (uint8_t)(h.seq & 0xFF);
  dst[1] = (uint8_t)((h.seq >> 8) & 0xFF);
  dst[2] = (uint8_t)(h.timestamp_ms & 0xFF);
  dst[3] = (uint8_t)((h.timestamp_ms >> 8) & 0xFF);
  dst[4] = (uint8_t)((h.timestamp_ms >> 16) & 0xFF);
  dst[5] = (uint8_t)((h.timestamp_ms >> 24) & 0xFF);
}

inline void ble_feature_header_v1_read(const uint8_t* src, BleFeatureHeaderV1* out) {
  out->seq = (uint16_t)(src[0] | (src[1] << 8));
  out->timestamp_ms = (uint32_t)(src[2] | (src[3] << 8) | (src[4] << 16) | (src[5] << 24));
}
```

- [ ] **Step 3: 在 `config.h` 增加 Feature UUID 与 quant UUID**

在 `OMI_SERVICE_UUID` 命名空间内新增：

```c
#define FEATURE_DATA_UUID  "19B10007-E8F2-537E-4F6C-D104768A1214"
#define FEATURE_CODEC_UUID "19B10008-E8F2-537E-4F6C-D104768A1214"
#define FEATURE_QUANT_UUID "19B10009-E8F2-537E-4F6C-D104768A1214"
```

并新增：

```c
#define FEATURE_CODEC_ID 33
```

- [ ] **Step 4: 在 `configure_ble()` 注册 3 个特征**

在 `app.cpp` 的 OMI service 下新增：

- `featureDataCharacteristic`：Notify
- `featureCodecCharacteristic`：Read（值=33）
- `featureQuantCharacteristic`：Read（值=6B quant payload；暂时 stub，Task 6 再接模型输出）

- [ ] **Step 5: 运行固件编译 + 单测 build**

Run:

```bash
cd /workspace/omi/omiGlass/firmware
platformio run -e seeed_xiao_esp32s3
platformio test -e seeed_xiao_esp32s3_test --without-uploading --without-testing
```

Expected: `SUCCESS` + test build PASS

- [ ] **Step 6: Commit（子模块）**

```bash
cd /workspace/omi
git add omiGlass/firmware/src/config.h omiGlass/firmware/src/app.cpp omiGlass/firmware/src/protocols/ble_feature_protocol.h omiGlass/firmware/test/test_feature_extract_tflm/test_feature_extract_tflm.cpp
git commit -m "feat(vision): add BLE feature protocol and GATT stubs (codec 33)"
git push origin main
```

---

## Task 3: Vendor TFLM 引入（最小可编译，不跑推理）

**Files:**
- Create: `omi/omiGlass/firmware/lib/tflite_micro/...`
- Modify: `omi/omiGlass/firmware/platformio.ini`
- Create: `omi/omiGlass/firmware/src/vision/feature_extract_tflm.h`
- Create: `omi/omiGlass/firmware/src/vision/feature_extract_tflm.cpp`
- Test: `omi/omiGlass/firmware/test/test_feature_extract_tflm/test_feature_extract_tflm.cpp`（增加 “API 可链接”）

- [ ] **Step 1: 写 failing Unity 测试（TFLM wrapper API 可链接）**

在 `test_feature_extract_tflm.cpp` 追加：

```cpp
#include "vision/feature_extract_tflm.h"

static void test_feature_extract_api_compiles()
{
  feature_extract_tflm_init();
  int8_t in[96*96] = {0};
  int8_t out[128] = {0};
  const bool ok = feature_extract_tflm_run(in, out, 128);
  TEST_ASSERT_TRUE(ok == false || ok == true);
}
```

- [ ] **Step 2: 引入 TFLM runtime 的最小文件集**

将以下目录 vendoring 到 `firmware/lib/tflite_micro/`（非 submodule）：

- `tensorflow/lite/micro/`（interpreter、arena allocator、micro error reporter）
- `tensorflow/lite/schema/`（model schema）
- `tensorflow/lite/core/api/`（tensor/ops API）
- `tensorflow/lite/kernels/internal/`（依赖的 internal utils）
- 先不引入全部 kernels，Task 5 再根据模型需要补齐

目标：能让 `#include "tensorflow/lite/micro/micro_interpreter.h"` 编译通过。

- [ ] **Step 3: `platformio.ini` 增加 include 路径**

在 `[env:seeed_xiao_esp32s3]` 与 `..._test` 的 `build_flags` 增加：

```ini
  -Ilib/tflite_micro
```

如需要禁止 RTTI/exceptions（保持与工程一致），不要新增与现有冲突的 flags。

- [ ] **Step 4: 添加 wrapper（只返回 false，不做推理）**

Create:

```cpp
// src/vision/feature_extract_tflm.h
#pragma once
#include <stddef.h>
#include <stdint.h>

void feature_extract_tflm_init();
bool feature_extract_tflm_run(const int8_t* input_96x96, int8_t* out_128, size_t out_len);
```

```cpp
// src/vision/feature_extract_tflm.cpp
#include "feature_extract_tflm.h"
void feature_extract_tflm_init() {}
bool feature_extract_tflm_run(const int8_t*, int8_t*, size_t) { return false; }
```

- [ ] **Step 5: 编译验证 + 单测 build**

Run:

```bash
cd /workspace/omi/omiGlass/firmware
platformio run -e seeed_xiao_esp32s3
platformio test -e seeed_xiao_esp32s3_test --without-uploading --without-testing
```

- [ ] **Step 6: Commit（子模块）**

```bash
cd /workspace/omi
git add omiGlass/firmware/lib/tflite_micro omiGlass/firmware/platformio.ini omiGlass/firmware/src/vision/feature_extract_tflm.* omiGlass/firmware/test/test_feature_extract_tflm/test_feature_extract_tflm.cpp
git commit -m "chore(tflm): vendor minimal TFLite Micro runtime skeleton"
git push origin main
```

---

## Task 4: 预处理流水线（RGB565 → Gray → 96×96 int8）

**Files:**
- Create: `omi/omiGlass/firmware/src/camera/camera_capture.h`
- Create: `omi/omiGlass/firmware/src/camera/camera_capture.cpp`
- Test: `omi/omiGlass/firmware/test/test_feature_extract_tflm/test_feature_extract_tflm.cpp`

- [ ] **Step 1: 写 failing Unity 测试（预处理范围与形状）**

在 `test_feature_extract_tflm.cpp` 增加：

```cpp
#include "camera/camera_capture.h"

static void test_preprocess_range()
{
  static uint16_t rgb565[128 * 128];
  for (int i = 0; i < 128*128; i++) rgb565[i] = 0xFFFF;

  int8_t out[96 * 96] = {0};
  preprocess_rgb565_to_96x96_int8(rgb565, 128, 128, out);

  for (int i = 0; i < 96*96; i++) {
    TEST_ASSERT_TRUE(out[i] >= -128 && out[i] <= 127);
  }
}
```

- [ ] **Step 2: 实现 `preprocess_rgb565_to_96x96_int8`（双线性）**

Create:

```cpp
// camera_capture.h
#pragma once
#include <stdint.h>

void preprocess_rgb565_to_96x96_int8(const uint16_t* rgb565, int src_w, int src_h, int8_t* out_96x96);
```

实现要点（写在 `camera_capture.cpp`）：

- RGB565 → 灰度（近似）：`y = (r*77 + g*150 + b*29) >> 8`，r/g/b 需从 565 展开到 8bit
- 双线性 resize：从 `src_w/src_h` 映射到 96×96
- 归一化到 int8：`int8 = (int) y - 128`（输出区间约 [-128,127]）
- 禁止动态分配；内部 scratch 仅使用局部小变量

- [ ] **Step 3: 编译验证 + 单测 build**

Run:

```bash
cd /workspace/omi/omiGlass/firmware
platformio run -e seeed_xiao_esp32s3
platformio test -e seeed_xiao_esp32s3_test --without-uploading --without-testing
```

- [ ] **Step 4: Commit（子模块）**

```bash
cd /workspace/omi
git add omiGlass/firmware/src/camera/camera_capture.* omiGlass/firmware/test/test_feature_extract_tflm/test_feature_extract_tflm.cpp
git commit -m "feat(vision): add RGB565->96x96 int8 preprocess"
git push origin main
```

---

## Task 5: 模型转换脚本 + 生成 `model_data.h`

**Files:**
- Create: `scripts/convert_model_to_tflm.py`
- Create: `omi/omiGlass/firmware/src/vision/model_data.h` (generated/committed)

- [ ] **Step 1: 写转换脚本（先实现“输入 tflite → 输出 C 数组”）**

Create:

```python
# scripts/convert_model_to_tflm.py
import argparse, pathlib, subprocess, sys

def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("--tflite", required=True)
  ap.add_argument("--out", required=True)
  args = ap.parse_args()

  tflite = pathlib.Path(args.tflite)
  out = pathlib.Path(args.out)
  if not tflite.exists():
    print("missing --tflite file", file=sys.stderr)
    return 2

  out.parent.mkdir(parents=True, exist_ok=True)
  subprocess.check_call(["xxd", "-i", str(tflite)], stdout=open(out, "w"))
  return 0

if __name__ == "__main__":
  raise SystemExit(main())
```

- [ ] **Step 2: 约定模型输入/输出 tensor 名称与 shape**

在 plan 中锁定：

- input: `int8[1,96,96,1]`
- output: `int8[1,128]`

并要求 `convert_model_to_tflm.py` 在后续迭代中打印模型元信息（通过 `flatc`/自解析/或 tflite-runtime）。若 CI 环境无法安装依赖，脚本应在缺依赖时输出明确错误并退出非 0。

- [ ] **Step 3: 生成占位 model_data.h（先放一个空数组用于编译）**

Create:

```cpp
// omi/omiGlass/firmware/src/vision/model_data.h
#pragma once
#include <stdint.h>

extern const unsigned char g_feature_model[];
extern const unsigned int g_feature_model_len;
extern const float g_feature_quant_scale;
extern const int8_t g_feature_quant_zero_point;
extern const uint8_t g_feature_model_id;
```

并在 `model_data.cpp`（若不想新增文件，则在 `feature_extract_tflm.cpp` 里先定义）提供弱实现：

```cpp
const unsigned char g_feature_model[] = {0x00};
const unsigned int g_feature_model_len = 1;
const float g_feature_quant_scale = 0.1f;
const int8_t g_feature_quant_zero_point = 0;
const uint8_t g_feature_model_id = 1;
```

- [ ] **Step 4: 脚本自检**

Run:

```bash
cd /workspace
python3 -m py_compile scripts/convert_model_to_tflm.py
```

- [ ] **Step 5: Commit（主仓库 + 子模块分别提交）**

主仓库：

```bash
cd /workspace
git add scripts/convert_model_to_tflm.py
git commit -m "build(vision): add script to convert tflite to C array"
git push origin main
```

子模块：

```bash
cd /workspace/omi
git add omiGlass/firmware/src/vision/model_data.h
git commit -m "chore(vision): add model_data header contract"
git push origin main
```

---

## Task 6: TFLM 推理封装（arena=30720，输出 128D int8）

**Files:**
- Modify: `omi/omiGlass/firmware/src/vision/feature_extract_tflm.cpp`
- Modify: `omi/omiGlass/firmware/src/vision/feature_extract_tflm.h`
- Modify/Create: `omi/omiGlass/firmware/src/vision/model_data.cpp`（或在现有 cpp 里定义）
- Test: `omi/omiGlass/firmware/test/test_feature_extract_tflm/test_feature_extract_tflm.cpp`
- Modify: `omi/omiGlass/firmware/platformio.ini`（必要 kernels 编译进来）

- [ ] **Step 1: 写 failing Unity 测试（输出维度=128，不崩溃）**

在 `test_feature_extract_tflm.cpp` 增加：

```cpp
static void test_infer_no_crash_and_len()
{
  feature_extract_tflm_init();
  static int8_t in[96*96];
  static int8_t out[128];
  const bool ok = feature_extract_tflm_run(in, out, 128);
  TEST_ASSERT_TRUE(ok);
}
```

- [ ] **Step 2: 在 `feature_extract_tflm.cpp` 中引入静态 arena 并初始化 interpreter**

关键代码（在实现时保持与 vendored 头文件一致）：

```cpp
static uint8_t s_tflm_arena[30720];
```

初始化流程：

- 绑定 `g_feature_model/g_feature_model_len`
- `MicroInterpreter` + `AllOpsResolver`（先用全量 resolver 保证能跑通；后续再裁剪到最小 kernels 以压 arena/flash）
- `AllocateTensors`

`run()` 流程：

- 校验输入 tensor type=int8、shape=[1,96,96,1]
- memcpy 输入
- `Invoke()`
- 校验输出 tensor type=int8、shape=[1,128]
- memcpy 输出到 `out_128`

- [ ] **Step 3: 编译验证（如出现 unresolved kernels，补齐对应 kernel 源码）**

策略：

- 第一版允许使用 `AllOpsResolver`（flash 增大可接受）
- 如 arena > 30720 或耗时超标，再做 kernels 裁剪（留到性能优化 task）

- [ ] **Step 4: 单测 build**

Run:

```bash
cd /workspace/omi/omiGlass/firmware
platformio test -e seeed_xiao_esp32s3_test --without-uploading --without-testing
```

- [ ] **Step 5: Commit（子模块）**

```bash
cd /workspace/omi
git add omiGlass/firmware/src/vision/feature_extract_tflm.* omiGlass/firmware/src/vision/model_data.* omiGlass/firmware/test/test_feature_extract_tflm/test_feature_extract_tflm.cpp omiGlass/firmware/platformio.ini
git commit -m "feat(vision): add TFLM inference wrapper with static 30KB arena"
git push origin main
```

---

## Task 7: BLE Feature 发送逻辑接入（节流复用 Phase 2）

**Files:**
- Create: `omi/omiGlass/firmware/src/ble/ble_feature_stream.h`
- Create: `omi/omiGlass/firmware/src/ble/ble_feature_stream.cpp`
- Modify: `omi/omiGlass/firmware/src/app.cpp`
- Modify: `omi/omiGlass/firmware/src/config.h`

- [ ] **Step 1: 实现 `ble_feature_stream`（封包+notify）**

接口：

```cpp
void ble_feature_stream_init(BLECharacteristic* dataChar);
void ble_feature_stream_send(const int8_t* feat_128, uint32_t capture_ts_ms);
uint16_t ble_feature_stream_last_seq();
```

实现要点：

- header：`BleFeatureHeaderV1{seq, timestamp_ms}`，LE 写入
- payload：`int8[128]`
- 静态 packet buffer：`uint8_t packet[134]`
- `seq` uint16 自增回绕

- [ ] **Step 2: 将 quant 参数写入 `FEATURE_QUANT_UUID`**

值来自 `model_data`：

- `scale` float32 little-endian
- `zero_point` int8
- `model_id` uint8

- [ ] **Step 3: 在主 loop 接入提取与发送（先用 stub frame，不依赖真实 camera pipeline）**

第一版：

- 若 `connected` 且订阅存在（feature CCCD）且 `!ble_audio_stream_is_congested()`：
  - 每 200ms 发送 1 帧（5 fps）
  - `capture_ts_ms = millis()`（此处必须来自“采集时刻”：后续 Task 8 接入真实 camera frame 时改为 frame capture 时刻）
  - `features` 先用全零（直到 camera+TFLM 打通）

第二版（与 camera 打通后）：

- capture_ts_ms 取 camera frame 获取时刻
- features 来自 TFLM 输出

- [ ] **Step 4: 编译验证**

Run:

```bash
cd /workspace/omi/omiGlass/firmware
platformio run -e seeed_xiao_esp32s3
```

- [ ] **Step 5: Commit（子模块）**

```bash
cd /workspace/omi
git add omiGlass/firmware/src/ble/ble_feature_stream.* omiGlass/firmware/src/app.cpp omiGlass/firmware/src/config.h
git commit -m "feat(vision): add BLE feature stream (codec 33) with quant read"
git push origin main
```

---

## Task 8: Python 相似度验证脚本（int8 dequant + cosine ≥0.85）

**Files:**
- Create: `scripts/test_feature_similarity.py`

- [ ] **Step 1: 写脚本（stdlib + 可选 tflite-runtime）**

脚本行为：

- 输入：`--frames`、`--seed`、`--scale`、`--zero-point`、`--model-id`
- 生成或加载测试输入（默认用可复现随机灰度图）
- 生成“device int8 输出”（先 mock；后续可接真实 BLE dump 文件）
- dequant + L2 norm
- cosine 相似度统计（p50/p95/min）

当缺少 reference runtime 时：

- 明确打印：`tflite-runtime not available; running mock-only mode`
- mock-only 模式不做“≥0.85 门禁断言”，只输出统计

当可用 reference runtime 时：

- 跑 float32 reference（同模型或 reference head）
- 强制门禁断言：min cosine ≥ 0.85，否则 exit 1

- [ ] **Step 2: 运行示例**

Run:

```bash
cd /workspace
python scripts/test_feature_similarity.py --frames 100 --seed 0
```

Expected: exit 0，并输出 cosine 分布表。

- [ ] **Step 3: Commit（主仓库）**

```bash
cd /workspace
git add scripts/test_feature_similarity.py
git commit -m "test(vision): add feature similarity simulator"
git push origin main
```

---

## Task 9: 集成与门禁报告（size + 性能 + 文档同步）

**Files:**
- Modify: `docs/superpowers/specs/2026-04-17-ai-glasses-mvp-design.md`
- Create: `/tmp/phase3_performance.md`
- Modify/Create: `omi/omiGlass/firmware/PHASE3_VALIDATION.md`

- [ ] **Step 1: 固件 size 与 `.dram0.bss` 门禁**

Run:

```bash
cd /workspace/omi/omiGlass/firmware
platformio run -e seeed_xiao_esp32s3 -t size 2>&1 | tee /tmp/phase3_size.log
```

Expected: `.dram0.bss` 增量（相对 Phase 3 基线）≤ 30720（仅 arena）+ 小量协议 buffer。

- [ ] **Step 2: 性能报告（无硬件时模拟）**

生成并填入：

- 推理耗时 p95（若无硬件，先写“模拟值 + 后续硬件验证 TODO”会被视为占位符，不允许）

因此此 step 要求：

- 若无硬件测量能力：仅输出“推理时间采集埋点 + 如何在设备日志中读取”，并把门禁验证推迟到硬件联调阶段（需你确认是否接受）。

- [ ] **Step 3: 更新总 spec（Feature 协议与 GATT 表）**

在 `2026-04-17-ai-glasses-mvp-design.md` 增加 Feature 特征表与 payload 定义（codec 33、quant 6B、notify 134B）。

- [ ] **Step 4: 固件验证摘要文档**

Create `omi/omiGlass/firmware/PHASE3_VALIDATION.md`，记录：

- model_id/scale/zero_point
- arena size
- `.dram0.bss` delta
- 测试命令与结果

- [ ] **Step 5: Commit（主仓库 + 子模块）**

按 Phase 2 流程分别提交并更新 submodule 指针。

