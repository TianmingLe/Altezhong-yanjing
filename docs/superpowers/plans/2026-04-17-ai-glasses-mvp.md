# AI Glasses MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于 BasedHardware/omi 实现“ESP32‑S3 眼镜 + Android/Flutter 手机 + FastAPI 云端”的 MVP 生产级闭环：音频/图像采集传输、任务下发与路由、手机端 AR/HUD 叠加预览、生产级 OTA（Ed25519 签名 + A/B + 5s 回滚语义）。

**Architecture:** 以现有 OmiGlass 固件与 OMI BLE 协议为兼容基线，在不破坏旧 App/旧固件的前提下新增 Task/HUD/Control GATT 特征与二进制协议层；手机端实现规则路由与 HUD 渲染（无屏 MVP）；后端新增视觉接口与 OTA URL 分发；PC 节点仅预留 relay 接口。

**Tech Stack:** ESP32‑S3 Arduino/PlatformIO（NimBLE-Arduino + esp32-camera + libopus），Flutter(Android)，FastAPI(Python)，协议：自定义二进制帧（CRC16-CCITT），OTA：Ed25519 验签 + A/B + 5s 回滚语义（ESP32 等价实现）。

---

## 0) 工作区与验证前置（必须先打通 Day 1 验收）

### Task 0: 开发环境自检与工具安装（本地/CI）

**Files:**
- Modify: 无（仅执行命令）

- [ ] **Step 1: 安装 PlatformIO（用于固件编译与单测）**

Run:
```bash
python -m pip install --upgrade pip
python -m pip install platformio
platformio --version
```
Expected: 输出 platformio 版本号。

- [ ] **Step 2: 固件零警告编译（Day 1 固件验收门槛）**

Run:
```bash
cd omi/omiGlass/firmware
platformio run -e seeed_xiao_esp32s3
```
Expected: Build SUCCESS，无 error；warning 需逐个消除（以 `-Wall`/编译器输出为准）。

- [ ] **Step 3: 后端测试可运行（Day 1 后端验收门槛）**

Run:
```bash
cd omi/backend
python -m pip install -r requirements.txt
python -m pytest -q
```
Expected: 全 PASS（若环境 Python 版本不兼容，优先用 `python3.11`/Docker 走同样命令，并将兼容性写入 README）。

- [ ] **Step 4: Flutter 工具链准备（Day 1 App 验收门槛）**

说明：本仓库 `omi/app` 使用 FVM（见 `.fvmrc`）。CI/本地需安装 Flutter SDK。

Run（本地推荐）:
```bash
cd omi/app
bash setup.sh android
flutter --version
flutter pub get
flutter build apk --debug
```
Expected: APK build success，可安装运行。

---

## 1) 协议与目录（P0：Phase 1）

### Task 1: 新增 protocols 目录（固件侧）并落地 HUD/Task/UUID 表头文件

**Files:**
- Create: `omi/omiGlass/firmware/src/protocols/ar_hud_protocol.h`
- Create: `omi/omiGlass/firmware/src/protocols/task_protocol.h`
- Create: `omi/omiGlass/firmware/src/protocols/ble_gatt_table.h`
- Create: `omi/omiGlass/firmware/src/protocols/ota_protocol.h`
- Test: `omi/omiGlass/firmware/test/test_protocols.cpp`

- [ ] **Step 1: 写 failing 单测（HUD 帧长度与字段编码）**

Create:
```cpp
// omi/omiGlass/firmware/test/test_protocols.cpp
#include <unity.h>

#include "protocols/ar_hud_protocol.h"
#include "protocols/task_protocol.h"

void test_hud_frame_pack_len_limit() {
    hud_frame_t f{};
    f.type = HUD_TYPE_TEXT;
    f.priority = 10;
    f.x = 100;
    f.y = 200;
    const char *msg = "hello";
    const size_t msg_len = 5;
    uint8_t out[HUD_FRAME_MAX_BYTES + 8] = {0};
    size_t out_len = 0;

    TEST_ASSERT_TRUE(hud_pack_text(&f, (const uint8_t*)msg, msg_len, out, sizeof(out), &out_len));
    TEST_ASSERT_EQUAL(7 + msg_len, out_len);
    TEST_ASSERT_TRUE(out_len <= HUD_FRAME_MAX_BYTES);
}

void test_hud_frame_pack_reject_too_long() {
    hud_frame_t f{};
    f.type = HUD_TYPE_TEXT;
    f.priority = 1;
    f.x = 0;
    f.y = 0;
    uint8_t payload[HUD_FRAME_MAX_BYTES] = {0};
    uint8_t out[HUD_FRAME_MAX_BYTES] = {0};
    size_t out_len = 0;

    // 58 bytes payload => 7+58=65 > 64 must fail
    TEST_ASSERT_FALSE(hud_pack_text(&f, payload, 58, out, sizeof(out), &out_len));
}

void test_crc16_ccitt_known_vector() {
    const uint8_t data[] = {0x01, 0x02, 0x03, 0x04};
    // 0x89C3 is the expected CRC16-CCITT (0xFFFF init) for this vector.
    TEST_ASSERT_EQUAL_HEX16(0x89C3, crc16_ccitt(data, sizeof(data)));
}

void setup() {
    UNITY_BEGIN();
    RUN_TEST(test_hud_frame_pack_len_limit);
    RUN_TEST(test_hud_frame_pack_reject_too_long);
    RUN_TEST(test_crc16_ccitt_known_vector);
    UNITY_END();
}

void loop() {}
```

- [ ] **Step 2: 运行测试，确认失败**

Run:
```bash
cd omi/omiGlass/firmware
platformio test -e seeed_xiao_esp32s3
```
Expected: FAIL（缺少头文件/函数未定义）。

- [ ] **Step 3: 写最小实现（协议头文件 + CRC16）**

Create:
```c
// omi/omiGlass/firmware/src/protocols/ar_hud_protocol.h
#pragma once

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

enum {
    HUD_FRAME_MAX_BYTES = 64,
};

typedef enum {
    HUD_TYPE_TEXT = 0,
    HUD_TYPE_ICON = 1,
    HUD_TYPE_TOAST = 2,
    HUD_TYPE_ALERT = 3,
} hud_type_t;

typedef struct __attribute__((packed)) {
    uint8_t type;
    uint8_t priority;
    uint16_t x;
    uint16_t y;
    uint8_t text_len;
} hud_frame_t;

static inline bool hud_pack_text(
    const hud_frame_t* in,
    const uint8_t* payload,
    size_t payload_len,
    uint8_t* out,
    size_t out_cap,
    size_t* out_len
) {
    if (!in || !out || !out_len) return false;
    if (payload_len > 57) return false;
    const size_t total = sizeof(hud_frame_t) + payload_len;
    if (total > HUD_FRAME_MAX_BYTES) return false;
    if (out_cap < total) return false;

    hud_frame_t hdr = *in;
    hdr.text_len = (uint8_t)payload_len;
    // little-endian fields already in native order on ESP32; keep packed struct copy
    __builtin_memcpy(out, &hdr, sizeof(hdr));
    if (payload_len > 0 && payload) __builtin_memcpy(out + sizeof(hdr), payload, payload_len);
    *out_len = total;
    return true;
}
```

Create:
```c
// omi/omiGlass/firmware/src/protocols/task_protocol.h
#pragma once

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

typedef enum {
    TASK_MSG_SUBMIT = 0x01,
    TASK_MSG_CANCEL = 0x02,
    TASK_MSG_ACK = 0x03,
    TASK_MSG_RESULT = 0x04,
    TASK_MSG_EVENT = 0x05,
} task_msg_type_t;

typedef struct __attribute__((packed)) {
    uint8_t ver;
    uint8_t msg_type;
    uint8_t flags;
    uint8_t reserved;
    uint32_t task_id;
    uint16_t payload_len;
    uint16_t crc16;
} task_msg_header_t;

typedef struct {
    const uint8_t* payload;
    size_t payload_len;
} task_msg_view_t;

uint16_t crc16_ccitt(const uint8_t* data, size_t len);

bool task_msg_pack(
    task_msg_type_t type,
    uint8_t flags,
    uint32_t task_id,
    const uint8_t* payload,
    uint16_t payload_len,
    uint8_t* out,
    size_t out_cap,
    size_t* out_len
);

bool task_msg_parse(const uint8_t* in, size_t in_len, task_msg_header_t* hdr_out, task_msg_view_t* view_out);
```

Create:
```c
// omi/omiGlass/firmware/src/protocols/ble_gatt_table.h
#pragma once

// Existing OMI service UUIDs (must match app/lib/services/devices/models.dart)
#define OMI_SERVICE_UUID "19B10000-E8F2-537E-4F6C-D104768A1214"
#define AUDIO_DATA_UUID "19B10001-E8F2-537E-4F6C-D104768A1214"
#define AUDIO_CODEC_UUID "19B10002-E8F2-537E-4F6C-D104768A1214"
#define PHOTO_DATA_UUID "19B10005-E8F2-537E-4F6C-D104768A1214"
#define PHOTO_CONTROL_UUID "19B10006-E8F2-537E-4F6C-D104768A1214"

// New V1.0 extensions (optional; App enables if present)
#define TASK_CONTROL_UUID "19B10020-E8F2-537E-4F6C-D104768A1214"
#define TASK_EVENT_UUID "19B10021-E8F2-537E-4F6C-D104768A1214"
#define HUD_FRAME_OUT_UUID "19B10022-E8F2-537E-4F6C-D104768A1214"
#define DEVICE_CONTROL_UUID "19B10023-E8F2-537E-4F6C-D104768A1214"
```

Create:
```c
// omi/omiGlass/firmware/src/protocols/ota_protocol.h
#pragma once

// Must match existing config.h & app/lib/services/devices/models.dart
enum {
    OTA_CMD_SET_WIFI = 0x01,
    OTA_CMD_START_OTA = 0x02,
    OTA_CMD_CANCEL_OTA = 0x03,
    OTA_CMD_GET_STATUS = 0x04,
    OTA_CMD_SET_URL = 0x05,
};

enum {
    OTA_STATUS_IDLE = 0x00,
    OTA_STATUS_WIFI_CONNECTING = 0x10,
    OTA_STATUS_WIFI_CONNECTED = 0x11,
    OTA_STATUS_WIFI_FAILED = 0x12,
    OTA_STATUS_DOWNLOADING = 0x20,
    OTA_STATUS_DOWNLOAD_COMPLETE = 0x21,
    OTA_STATUS_DOWNLOAD_FAILED = 0x22,
    OTA_STATUS_INSTALLING = 0x30,
    OTA_STATUS_INSTALL_COMPLETE = 0x31,
    OTA_STATUS_INSTALL_FAILED = 0x32,
    OTA_STATUS_REBOOTING = 0x40,
    OTA_STATUS_ERROR = 0xFF,
};
```

Create:
```c
// omi/omiGlass/firmware/src/protocols/task_protocol.cpp
#include "protocols/task_protocol.h"

static uint16_t crc16_step(uint16_t crc, uint8_t b) {
    crc ^= (uint16_t)b << 8;
    for (int i = 0; i < 8; i++) {
        crc = (crc & 0x8000) ? (crc << 1) ^ 0x1021 : (crc << 1);
    }
    return crc;
}

uint16_t crc16_ccitt(const uint8_t* data, size_t len) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < len; i++) crc = crc16_step(crc, data[i]);
    return crc;
}

bool task_msg_pack(
    task_msg_type_t type,
    uint8_t flags,
    uint32_t task_id,
    const uint8_t* payload,
    uint16_t payload_len,
    uint8_t* out,
    size_t out_cap,
    size_t* out_len
) {
    if (!out || !out_len) return false;
    const size_t total = sizeof(task_msg_header_t) + payload_len;
    if (out_cap < total) return false;

    task_msg_header_t hdr{};
    hdr.ver = 1;
    hdr.msg_type = (uint8_t)type;
    hdr.flags = flags;
    hdr.task_id = task_id;
    hdr.payload_len = payload_len;
    hdr.crc16 = 0;

    __builtin_memcpy(out, &hdr, sizeof(hdr));
    if (payload_len > 0 && payload) __builtin_memcpy(out + sizeof(hdr), payload, payload_len);

    const uint16_t crc = crc16_ccitt(out, sizeof(hdr) - sizeof(hdr.crc16) + payload_len);
    // write crc16 into header (little-endian)
    out[offsetof(task_msg_header_t, crc16) + 0] = (uint8_t)(crc & 0xFF);
    out[offsetof(task_msg_header_t, crc16) + 1] = (uint8_t)((crc >> 8) & 0xFF);

    *out_len = total;
    return true;
}

bool task_msg_parse(const uint8_t* in, size_t in_len, task_msg_header_t* hdr_out, task_msg_view_t* view_out) {
    if (!in || in_len < sizeof(task_msg_header_t) || !hdr_out || !view_out) return false;
    task_msg_header_t hdr{};
    __builtin_memcpy(&hdr, in, sizeof(hdr));
    if (hdr.ver != 1) return false;
    if (in_len < sizeof(task_msg_header_t) + hdr.payload_len) return false;

    uint8_t tmp_hdr[sizeof(task_msg_header_t)] = {0};
    __builtin_memcpy(tmp_hdr, in, sizeof(task_msg_header_t));
    tmp_hdr[offsetof(task_msg_header_t, crc16) + 0] = 0;
    tmp_hdr[offsetof(task_msg_header_t, crc16) + 1] = 0;

    const size_t crc_input_len = (sizeof(task_msg_header_t) - sizeof(hdr.crc16)) + hdr.payload_len;
    uint8_t buf[sizeof(task_msg_header_t) + 256] = {0};
    if (hdr.payload_len > 256) return false;
    __builtin_memcpy(buf, tmp_hdr, sizeof(task_msg_header_t));
    __builtin_memcpy(buf + sizeof(task_msg_header_t), in + sizeof(task_msg_header_t), hdr.payload_len);
    const uint16_t crc = crc16_ccitt(buf, crc_input_len);
    if (crc != hdr.crc16) return false;

    *hdr_out = hdr;
    view_out->payload = in + sizeof(task_msg_header_t);
    view_out->payload_len = hdr.payload_len;
    return true;
}
```

- [ ] **Step 4: 让单测通过**

Modify `platformio.ini` 让测试能编译协议实现文件（PlatformIO 默认会编译 `src`，确保 `task_protocol.cpp` 在 `src/` 下）。

Run:
```bash
cd omi/omiGlass/firmware
platformio test -e seeed_xiao_esp32s3
```
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add omi/omiGlass/firmware/src/protocols omi/omiGlass/firmware/test/test_protocols.cpp
git commit -m "feat(firmware): add hud/task binary protocols and tests"
```

---

## 2) Display HAL（P0：Phase 1 补齐“无屏抽象”）

### Task 2: 添加 display stub（严禁耦合显示驱动）

**Files:**
- Create: `omi/omiGlass/firmware/src/display/display_hal.h`
- Create: `omi/omiGlass/firmware/src/display/display_hal.cpp`
- Test: `omi/omiGlass/firmware/test/test_display_hal.cpp`

- [ ] **Step 1: failing test（可链接 + 空实现不崩）**

Create:
```cpp
// omi/omiGlass/firmware/test/test_display_hal.cpp
#include <unity.h>
#include "display/display_hal.h"

void test_display_stub_links() {
    display_init();
    hud_frame_t f{};
    f.type = HUD_TYPE_TEXT;
    f.priority = 0;
    f.x = 0;
    f.y = 0;
    display_render(&f);
    display_clear();
    TEST_ASSERT_TRUE(true);
}

void setup() {
    UNITY_BEGIN();
    RUN_TEST(test_display_stub_links);
    UNITY_END();
}

void loop() {}
```

- [ ] **Step 2: 最小实现**

Create:
```c
// omi/omiGlass/firmware/src/display/display_hal.h
#pragma once

#include "protocols/ar_hud_protocol.h"

void display_init(void);
void display_render(const hud_frame_t* f);
void display_clear(void);
```

Create:
```c
// omi/omiGlass/firmware/src/display/display_hal.cpp
#include "display/display_hal.h"

void display_init(void) {}
void display_render(const hud_frame_t* f) {(void)f;}
void display_clear(void) {}
```

- [ ] **Step 3: 运行测试**

Run:
```bash
cd omi/omiGlass/firmware
platformio test -e seeed_xiao_esp32s3
```
Expected: PASS。

---

## 3) BLE GATT 扩展（P0：Phase 1/2）

### Task 3: 固件新增 Task/HUD/DeviceControl 特征（保持旧协议兼容）

**Files:**
- Create: `omi/omiGlass/firmware/src/gatt/omi_gatt_service.h`
- Create: `omi/omiGlass/firmware/src/gatt/omi_gatt_service.cpp`
- Modify: `omi/omiGlass/firmware/src/app.cpp`（把 BLE 初始化移入新模块/或在原位插入新增特征）
- Test: `omi/omiGlass/firmware/test/test_task_msg.cpp`

- [ ] **Step 1: failing test（Task 消息 pack/parse 循环）**

Create:
```cpp
// omi/omiGlass/firmware/test/test_task_msg.cpp
#include <unity.h>
#include "protocols/task_protocol.h"

void test_task_pack_parse_roundtrip() {
    const uint8_t payload[] = {0x01, 0x02, 0x03};
    uint8_t out[64] = {0};
    size_t out_len = 0;
    TEST_ASSERT_TRUE(task_msg_pack(TASK_MSG_SUBMIT, 0x01, 123, payload, sizeof(payload), out, sizeof(out), &out_len));

    task_msg_header_t hdr{};
    task_msg_view_t view{};
    TEST_ASSERT_TRUE(task_msg_parse(out, out_len, &hdr, &view));
    TEST_ASSERT_EQUAL_UINT8(1, hdr.ver);
    TEST_ASSERT_EQUAL_UINT8(TASK_MSG_SUBMIT, hdr.msg_type);
    TEST_ASSERT_EQUAL_UINT32(123, hdr.task_id);
    TEST_ASSERT_EQUAL_UINT16(sizeof(payload), hdr.payload_len);
    TEST_ASSERT_EQUAL_UINT8_ARRAY(payload, view.payload, sizeof(payload));
}

void setup() {
    UNITY_BEGIN();
    RUN_TEST(test_task_pack_parse_roundtrip);
    UNITY_END();
}

void loop() {}
```

- [ ] **Step 2: 最小实现 GATT 模块（只注册特征，回调先 echo ACK）**

Create:
```c
// omi/omiGlass/firmware/src/gatt/omi_gatt_service.h
#pragma once

#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLECharacteristic.h>

typedef struct {
    BLECharacteristic* task_control;
    BLECharacteristic* task_event;
    BLECharacteristic* hud_out;
    BLECharacteristic* device_control;
} omi_ext_chars_t;

omi_ext_chars_t omi_gatt_register_extensions(BLEServer* server);
```

Create:
```c
// omi/omiGlass/firmware/src/gatt/omi_gatt_service.cpp
#include "gatt/omi_gatt_service.h"

#include <BLE2902.h>

#include "protocols/ble_gatt_table.h"
#include "protocols/task_protocol.h"

static BLECharacteristic* g_task_event = nullptr;

class TaskControlCallback : public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic* c) override {
        std::string v = c->getValue();
        if (!g_task_event) return;

        task_msg_header_t hdr{};
        task_msg_view_t view{};
        const bool ok = task_msg_parse((const uint8_t*)v.data(), v.size(), &hdr, &view);
        if (!ok) return;

        uint8_t out[32] = {0};
        size_t out_len = 0;
        task_msg_pack(TASK_MSG_ACK, 0x00, hdr.task_id, nullptr, 0, out, sizeof(out), &out_len);
        g_task_event->setValue(out, out_len);
        g_task_event->notify();
    }
};

omi_ext_chars_t omi_gatt_register_extensions(BLEServer* server) {
    omi_ext_chars_t r{};
    auto* svc = server->getServiceByUUID(OMI_SERVICE_UUID);
    if (!svc) return r;

    r.task_control = svc->createCharacteristic(TASK_CONTROL_UUID, BLECharacteristic::PROPERTY_WRITE_NR | BLECharacteristic::PROPERTY_WRITE);
    r.task_event = svc->createCharacteristic(TASK_EVENT_UUID, BLECharacteristic::PROPERTY_NOTIFY);
    r.hud_out = svc->createCharacteristic(HUD_FRAME_OUT_UUID, BLECharacteristic::PROPERTY_NOTIFY);
    r.device_control = svc->createCharacteristic(DEVICE_CONTROL_UUID, BLECharacteristic::PROPERTY_WRITE_NR | BLECharacteristic::PROPERTY_WRITE);

    r.task_control->setCallbacks(new TaskControlCallback());
    r.task_event->addDescriptor(new BLE2902());
    r.hud_out->addDescriptor(new BLE2902());

    g_task_event = r.task_event;
    return r;
}
```

- [ ] **Step 3: 把注册函数接入 app.cpp（不改变现有音频/图片/OTA 特征）**

Modify：在现有 BLE 服务创建完成后调用 `omi_gatt_register_extensions(server)`。

- [ ] **Step 4: 跑固件编译 + 单测**

Run:
```bash
cd omi/omiGlass/firmware
platformio run -e seeed_xiao_esp32s3
platformio test -e seeed_xiao_esp32s3
```

### Task 3.1: BLE MTU/PHY 协商与日志（P0：可观测性与稳定性）

**Files:**
- Create: `omi/omiGlass/firmware/src/gatt/gatt_mtu_phy.h`
- Create: `omi/omiGlass/firmware/src/gatt/gatt_mtu_phy.cpp`
- Modify: `omi/omiGlass/firmware/src/app.cpp`（在连接回调里调用）

- [ ] **Step 1: 实现最小 API（协商完成后打印 MTU/PHY，并在 MTU<251 打 Warning）**

Create:
```c
// omi/omiGlass/firmware/src/gatt/gatt_mtu_phy.h
#pragma once

#include <stdint.h>

void gatt_log_link_params(uint16_t mtu, bool phy2m);
```

Create:
```c
// omi/omiGlass/firmware/src/gatt/gatt_mtu_phy.cpp
#include "gatt/gatt_mtu_phy.h"

#include <Arduino.h>

void gatt_log_link_params(uint16_t mtu, bool phy2m) {
    if (mtu < 251) {
        Serial.printf("BLE: MTU negotiated to %u (<251), throughput may be limited\n", mtu);
    } else {
        Serial.printf("BLE: MTU=%u\n", mtu);
    }
    Serial.printf("BLE: PHY=%s\n", phy2m ? "2M" : "1M");
}
```

- [ ] **Step 2: 在 BLE onConnect / onMTUChange / onPhyUpdate（若可用）接入日志**

Modify `app.cpp`：在 NimBLE 回调里获取当前 MTU；PHY 能力按平台可得性判断（不可得则传 `false`，并在 Task Event 上报能力缺失）。

---
---


### Task 4: Flutter 端实现 HUD 二进制帧编解码（≤64B）+ 单测

**Files:**
- Create: `omi/app/lib/services/hud/hud_protocol.dart`
- Test: `omi/app/test/hud_protocol_test.dart`

- [ ] **Step 1: 写 failing test（帧解析/编码）**

Create:
```dart
// omi/app/test/hud_protocol_test.dart
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:omi/services/hud/hud_protocol.dart';

void main() {
  test('hud pack/unpack roundtrip', () {
    final msg = 'hello';
    final frame = HudFrame.text(priority: 10, x: 100, y: 200, text: msg);
    final bytes = HudProtocol.encode(frame);
    expect(bytes.length, 7 + msg.length);
    expect(bytes.length <= 64, true);

    final decoded = HudProtocol.decode(Uint8List.fromList(bytes));
    expect(decoded.type, HudType.text);
    expect(decoded.priority, 10);
    expect(decoded.x, 100);
    expect(decoded.y, 200);
    expect(decoded.text, msg);
  });

  test('hud rejects >64 bytes', () {
    final longText = 'a' * 58;
    expect(() => HudProtocol.encode(HudFrame.text(priority: 0, x: 0, y: 0, text: longText)), throwsArgumentError);
  });
}
```

- [ ] **Step 2: 最小实现**

Create:
```dart
// omi/app/lib/services/hud/hud_protocol.dart
import 'dart:convert';
import 'dart:typed_data';

enum HudType { text, icon, toast, alert }

class HudFrame {
  final HudType type;
  final int priority;
  final int x;
  final int y;
  final Uint8List payload;

  const HudFrame({
    required this.type,
    required this.priority,
    required this.x,
    required this.y,
    required this.payload,
  });

  String get text => utf8.decode(payload, allowMalformed: true);

  factory HudFrame.text({required int priority, required int x, required int y, required String text}) {
    final bytes = utf8.encode(text);
    return HudFrame(
      type: HudType.text,
      priority: priority,
      x: x,
      y: y,
      payload: Uint8List.fromList(bytes),
    );
  }
}

class HudProtocol {
  static const int maxBytes = 64;

  static List<int> encode(HudFrame f) {
    final textLen = f.payload.length;
    final total = 7 + textLen;
    if (total > maxBytes) throw ArgumentError('HUD frame too large: $total');

    final b = BytesBuilder(copy: false);
    b.addByte(f.type.index & 0xFF);
    b.addByte(f.priority & 0xFF);
    b.add(_u16le(f.x));
    b.add(_u16le(f.y));
    b.addByte(textLen & 0xFF);
    b.add(f.payload);
    return b.toBytes();
  }

  static HudFrame decode(Uint8List bytes) {
    if (bytes.length < 7) throw ArgumentError('HUD frame too short');
    if (bytes.length > maxBytes) throw ArgumentError('HUD frame too large');

    final type = HudType.values[bytes[0]];
    final priority = bytes[1];
    final x = _leU16(bytes, 2);
    final y = _leU16(bytes, 4);
    final len = bytes[6];
    if (7 + len != bytes.length) throw ArgumentError('Invalid HUD length');
    final payload = Uint8List.sublistView(bytes, 7, 7 + len);
    return HudFrame(type: type, priority: priority, x: x, y: y, payload: payload);
  }

  static List<int> _u16le(int v) => [v & 0xFF, (v >> 8) & 0xFF];
  static int _leU16(Uint8List b, int o) => b[o] | (b[o + 1] << 8);
}
```

- [ ] **Step 3: 运行测试**

Run:
```bash
cd omi/app
flutter test test/hud_protocol_test.dart
```
Expected: PASS。

### Task 4.1: Flutter 端 HUD WebSocket（loopback）+ 预览叠加控制器（满足“BLE→WS→渲染”链路）

**Files:**
- Create: `omi/app/lib/services/hud/hud_ws_server.dart`
- Create: `omi/app/lib/services/hud/hud_ws_client.dart`
- Create: `omi/app/lib/services/hud/hud_overlay_controller.dart`
- Test: `omi/app/test/hud_ws_loopback_test.dart`

- [ ] **Step 1: failing test（本地 WS server/client 循环转发二进制 HUD 帧）**

Create:
```dart
// omi/app/test/hud_ws_loopback_test.dart
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:omi/services/hud/hud_protocol.dart';
import 'package:omi/services/hud/hud_ws_server.dart';
import 'package:omi/services/hud/hud_ws_client.dart';

void main() {
  test('hud ws loopback', () async {
    final server = HudWsServer(host: '127.0.0.1', port: 0);
    final url = await server.start();
    final client = HudWsClient(url: url);

    final received = <Uint8List>[];
    final sub = client.frames.listen(received.add);
    await client.connect();

    final frame = HudFrame.text(priority: 1, x: 10, y: 20, text: 'ok');
    final bytes = Uint8List.fromList(HudProtocol.encode(frame));
    await server.broadcast(bytes);

    await Future<void>.delayed(const Duration(milliseconds: 50));
    expect(received.isNotEmpty, true);
    expect(received.first, bytes);

    await sub.cancel();
    await client.close();
    await server.stop();
  });
}
```

- [ ] **Step 2: 最小实现 server/client（不新增三方依赖，使用 dart:io + 已有 web_socket_channel）**

Create:
```dart
// omi/app/lib/services/hud/hud_ws_server.dart
import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

class HudWsServer {
  final String host;
  final int port;

  HttpServer? _server;
  final _sockets = <WebSocket>{};

  HudWsServer({required this.host, required this.port});

  Future<String> start() async {
    final server = await HttpServer.bind(host, port);
    _server = server;
    server.listen((req) async {
      if (!WebSocketTransformer.isUpgradeRequest(req)) {
        req.response.statusCode = HttpStatus.notFound;
        await req.response.close();
        return;
      }
      final socket = await WebSocketTransformer.upgrade(req);
      _sockets.add(socket);
      socket.listen(
        (_) {},
        onDone: () => _sockets.remove(socket),
        onError: (_) => _sockets.remove(socket),
        cancelOnError: true,
      );
    });
    return 'ws://${server.address.host}:${server.port}';
  }

  Future<void> broadcast(Uint8List bytes) async {
    for (final s in _sockets.toList()) {
      try {
        s.add(bytes);
      } catch (_) {
        _sockets.remove(s);
      }
    }
  }

  Future<void> stop() async {
    for (final s in _sockets.toList()) {
      try {
        await s.close();
      } catch (_) {}
    }
    _sockets.clear();
    await _server?.close(force: true);
    _server = null;
  }
}
```

Create:
```dart
// omi/app/lib/services/hud/hud_ws_client.dart
import 'dart:async';
import 'dart:typed_data';

import 'package:web_socket_channel/io.dart';

class HudWsClient {
  final String url;
  IOWebSocketChannel? _ch;
  final _frames = StreamController<Uint8List>.broadcast();

  Stream<Uint8List> get frames => _frames.stream;

  HudWsClient({required this.url});

  Future<void> connect() async {
    _ch = IOWebSocketChannel.connect(url);
    _ch!.stream.listen((m) {
      if (m is List<int>) _frames.add(Uint8List.fromList(m));
      if (m is Uint8List) _frames.add(m);
    });
    await _ch!.ready;
  }

  Future<void> close() async {
    await _ch?.sink.close();
    _ch = null;
    await _frames.close();
  }
}
```

- [ ] **Step 3: 运行测试**

Run:
```bash
cd omi/app
flutter test test/hud_ws_loopback_test.dart
```

---

## 5) 任务路由最小闭环（P0：Phase 2）

### Task 5: 手机端 Task 二进制协议实现 + 规则路由骨架 + 单测

**Files:**
- Create: `omi/app/lib/services/router/task_protocol.dart`
- Create: `omi/app/lib/services/router/task_models.dart`
- Test: `omi/app/test/task_protocol_test.dart`

- [ ] **Step 1: failing test（pack/parse roundtrip + crc16）**

Create:
```dart
// omi/app/test/task_protocol_test.dart
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:omi/services/router/task_protocol.dart';

void main() {
  test('task pack/parse roundtrip', () {
    final payload = Uint8List.fromList([1, 2, 3]);
    final msg = TaskMsg.submit(taskId: 123, flags: 1, payload: payload);
    final bytes = TaskProtocol.encode(msg);
    final parsed = TaskProtocol.decode(Uint8List.fromList(bytes));
    expect(parsed.header.ver, 1);
    expect(parsed.header.msgType, TaskMsgType.submit);
    expect(parsed.header.taskId, 123);
    expect(parsed.payload, payload);
  });
}
```

- [ ] **Step 2: 最小实现（与固件头对齐）**

Create:
```dart
// omi/app/lib/services/router/task_models.dart
import 'dart:typed_data';

enum TaskMsgType { submit, cancel, ack, result, event }

class TaskHeader {
  final int ver;
  final TaskMsgType msgType;
  final int flags;
  final int taskId;
  final int payloadLen;
  final int crc16;

  const TaskHeader({
    required this.ver,
    required this.msgType,
    required this.flags,
    required this.taskId,
    required this.payloadLen,
    required this.crc16,
  });
}

class TaskMsg {
  final TaskHeader header;
  final Uint8List payload;

  const TaskMsg({required this.header, required this.payload});

  factory TaskMsg.submit({required int taskId, required int flags, required Uint8List payload}) {
    return TaskMsg(
      header: TaskHeader(ver: 1, msgType: TaskMsgType.submit, flags: flags, taskId: taskId, payloadLen: payload.length, crc16: 0),
      payload: payload,
    );
  }
}
```

Create:
```dart
// omi/app/lib/services/router/task_protocol.dart
import 'dart:typed_data';
import 'task_models.dart';

class TaskProtocol {
  static List<int> encode(TaskMsg msg) {
    final payload = msg.payload;
    final hdr = BytesBuilder(copy: false);
    hdr.addByte(1);
    hdr.addByte(_typeToByte(msg.header.msgType));
    hdr.addByte(msg.header.flags & 0xFF);
    hdr.addByte(0);
    hdr.add(_u32le(msg.header.taskId));
    hdr.add(_u16le(payload.length));
    hdr.add([0, 0]);
    final tmp = hdr.toBytes();
    final all = BytesBuilder(copy: false)..add(tmp)..add(payload);
    final bytes = all.toBytes();
    final crc = crc16Ccitt(bytes.sublist(0, 12 + payload.length));
    bytes[12] = crc & 0xFF;
    bytes[13] = (crc >> 8) & 0xFF;
    return bytes;
  }

  static TaskMsg decode(Uint8List bytes) {
    if (bytes.length < 14) throw ArgumentError('too short');
    final ver = bytes[0];
    if (ver != 1) throw ArgumentError('bad ver');
    final msgType = _byteToType(bytes[1]);
    final flags = bytes[2];
    final taskId = _leU32(bytes, 4);
    final payloadLen = _leU16(bytes, 8);
    final crc = _leU16(bytes, 12);
    if (bytes.length != 14 + payloadLen) throw ArgumentError('len mismatch');
    final tmp = Uint8List.fromList(bytes);
    tmp[12] = 0;
    tmp[13] = 0;
    final expect = crc16Ccitt(tmp.sublist(0, 12 + payloadLen));
    if (expect != crc) throw ArgumentError('crc mismatch');
    final payload = Uint8List.sublistView(bytes, 14, 14 + payloadLen);
    return TaskMsg(
      header: TaskHeader(ver: ver, msgType: msgType, flags: flags, taskId: taskId, payloadLen: payloadLen, crc16: crc),
      payload: Uint8List.fromList(payload),
    );
  }

  static int crc16Ccitt(List<int> data) {
    var crc = 0xFFFF;
    for (final b in data) {
      crc ^= (b & 0xFF) << 8;
      for (var i = 0; i < 8; i++) {
        crc = (crc & 0x8000) != 0 ? ((crc << 1) ^ 0x1021) & 0xFFFF : (crc << 1) & 0xFFFF;
      }
    }
    return crc & 0xFFFF;
  }

  static List<int> _u16le(int v) => [v & 0xFF, (v >> 8) & 0xFF];
  static List<int> _u32le(int v) => [v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF, (v >> 24) & 0xFF];
  static int _leU16(Uint8List b, int o) => b[o] | (b[o + 1] << 8);
  static int _leU32(Uint8List b, int o) => b[o] | (b[o + 1] << 8) | (b[o + 2] << 16) | (b[o + 3] << 24);

  static int _typeToByte(TaskMsgType t) => switch (t) {
        TaskMsgType.submit => 0x01,
        TaskMsgType.cancel => 0x02,
        TaskMsgType.ack => 0x03,
        TaskMsgType.result => 0x04,
        TaskMsgType.event => 0x05,
      };

  static TaskMsgType _byteToType(int b) => switch (b) {
        0x01 => TaskMsgType.submit,
        0x02 => TaskMsgType.cancel,
        0x03 => TaskMsgType.ack,
        0x04 => TaskMsgType.result,
        0x05 => TaskMsgType.event,
        _ => throw ArgumentError('bad type'),
      };
}
```

- [ ] **Step 3: 运行测试**

Run:
```bash
cd omi/app
flutter test test/task_protocol_test.dart
```

---

## 5.1) UUID 同步校验脚本（P0：避免协议分裂）

### Task 5.1: 增加 scripts/sync_uuids.py 与 pytest（固件 ble_gatt_table.h ↔ App models.dart）

**Files:**
- Create: `omi/scripts/sync_uuids.py`
- Create: `omi/backend/tests/test_uuid_sync.py`

- [ ] **Step 1: failing test（UUID 不一致时失败，一致时通过）**

Create:
```python
# omi/backend/tests/test_uuid_sync.py
from pathlib import Path

from omi.scripts.sync_uuids import extract_fw_uuids, extract_app_uuids


def test_uuid_tables_match():
    root = Path(__file__).resolve().parents[2]
    fw = root / "omiGlass" / "firmware" / "src" / "protocols" / "ble_gatt_table.h"
    app = root / "app" / "lib" / "services" / "devices" / "models.dart"
    fw_map = extract_fw_uuids(fw.read_text(encoding="utf-8"))
    app_map = extract_app_uuids(app.read_text(encoding="utf-8"))

    # Compare only the UUIDs we own in the OMI namespace
    for k, v in fw_map.items():
        assert app_map.get(k) == v
```

- [ ] **Step 2: 最小实现脚本（只解析 #define 与 const String）**

Create:
```python
# omi/scripts/sync_uuids.py
import re
from typing import Dict


FW_RE = re.compile(r'#define\s+([A-Z0-9_]+)\s+"([0-9A-Fa-f-]{36})"')
APP_RE = re.compile(r"const\s+String\s+([a-zA-Z0-9_]+)\s*=\s*'([0-9A-Fa-f-]{36})';")


def extract_fw_uuids(text: str) -> Dict[str, str]:
    return {m.group(1): m.group(2).lower() for m in FW_RE.finditer(text)}


def extract_app_uuids(text: str) -> Dict[str, str]:
    raw = {m.group(1): m.group(2).lower() for m in APP_RE.finditer(text)}
    # Map app names to firmware #define names where needed
    mapping = {
        "omiServiceUuid": "OMI_SERVICE_UUID",
        "audioDataStreamCharacteristicUuid": "AUDIO_DATA_UUID",
        "audioCodecCharacteristicUuid": "AUDIO_CODEC_UUID",
        "imageDataStreamCharacteristicUuid": "PHOTO_DATA_UUID",
        "imageCaptureControlCharacteristicUuid": "PHOTO_CONTROL_UUID",
    }
    out: Dict[str, str] = {}
    for app_key, fw_key in mapping.items():
        if app_key in raw:
            out[fw_key] = raw[app_key]
    return out
```

- [ ] **Step 3: 运行后端测试**

Run:
```bash
cd omi/backend
python -m pytest -q tests/test_uuid_sync.py
```

---

## 5.2) 固件侧带宽节流与优先级（P0：音频优先，JPEG/HUD 不抢占）

### Task 5.2: 新增 scheduler/policy_rules 里最小节流策略 + 单测

**Files:**
- Create: `omi/omiGlass/firmware/src/scheduler/policy_rules.h`
- Create: `omi/omiGlass/firmware/src/scheduler/policy_rules.cpp`
- Test: `omi/omiGlass/firmware/test/test_policy_rules.cpp`
- Modify: `omi/omiGlass/firmware/src/app.cpp`（在发送 JPEG 分片前调用 allow_*）

- [ ] **Step 1: failing test（音频活动时，JPEG 发送被限速）**

Create:
```cpp
// omi/omiGlass/firmware/test/test_policy_rules.cpp
#include <unity.h>
#include "scheduler/policy_rules.h"

void test_jpeg_throttled_when_audio_active() {
    policy_state_t s{};
    s.audio_active = true;
    s.last_jpeg_ms = 0;
    TEST_ASSERT_FALSE(policy_allow_jpeg_send(&s, 100));
    s.audio_active = false;
    TEST_ASSERT_TRUE(policy_allow_jpeg_send(&s, 100));
}

void setup() {
    UNITY_BEGIN();
    RUN_TEST(test_jpeg_throttled_when_audio_active);
    UNITY_END();
}

void loop() {}
```

- [ ] **Step 2: 最小实现（纯时间窗 + 音频优先）**

Create:
```c
// omi/omiGlass/firmware/src/scheduler/policy_rules.h
#pragma once

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    bool audio_active;
    uint32_t last_jpeg_ms;
} policy_state_t;

bool policy_allow_jpeg_send(policy_state_t* s, uint32_t now_ms);
```

Create:
```c
// omi/omiGlass/firmware/src/scheduler/policy_rules.cpp
#include "scheduler/policy_rules.h"

// When audio is streaming, JPEG is heavily throttled to avoid BLE congestion.
static const uint32_t JPEG_MIN_INTERVAL_MS_WHEN_AUDIO = 1500;
static const uint32_t JPEG_MIN_INTERVAL_MS_IDLE = 200;

bool policy_allow_jpeg_send(policy_state_t* s, uint32_t now_ms) {
    if (!s) return false;
    const uint32_t min_int = s->audio_active ? JPEG_MIN_INTERVAL_MS_WHEN_AUDIO : JPEG_MIN_INTERVAL_MS_IDLE;
    if (now_ms - s->last_jpeg_ms < min_int) return false;
    s->last_jpeg_ms = now_ms;
    return true;
}
```

- [ ] **Step 3: 接入 app.cpp 发送 JPEG 分片路径**

Modify：在进入 JPEG 发送循环前检查 `policy_allow_jpeg_send(...)`，不允许则跳过本次发送。

- [ ] **Step 4: 运行固件测试**

Run:
```bash
cd omi/omiGlass/firmware
platformio test -e seeed_xiao_esp32s3 -f test_policy_rules
```

---

## 5.3) ESP32 内存池分时复用（P0：应对 RNNoise + TFLM 峰值）

### Task 5.3: 预留 shared_arena（不引入 RNNoise/TFLM 实现前先落接口与统计）

**Files:**
- Create: `omi/omiGlass/firmware/src/memory/shared_arena.h`
- Create: `omi/omiGlass/firmware/src/memory/shared_arena.cpp`
- Test: `omi/omiGlass/firmware/test/test_shared_arena.cpp`

- [ ] **Step 1: failing test（申请/释放与峰值统计）**

Create:
```cpp
// omi/omiGlass/firmware/test/test_shared_arena.cpp
#include <unity.h>
#include "memory/shared_arena.h"

void test_arena_alloc_free_peak() {
    shared_arena_init(4096);
    void* a = shared_arena_alloc(1024);
    TEST_ASSERT_NOT_NULL(a);
    void* b = shared_arena_alloc(1024);
    TEST_ASSERT_NOT_NULL(b);
    shared_arena_free_all();
    TEST_ASSERT_EQUAL_UINT32(2048, shared_arena_peak_bytes());
}

void setup() {
    UNITY_BEGIN();
    RUN_TEST(test_arena_alloc_free_peak);
    UNITY_END();
}

void loop() {}
```

- [ ] **Step 2: 最小实现（单块 bump allocator + free_all）**

Create:
```c
// omi/omiGlass/firmware/src/memory/shared_arena.h
#pragma once

#include <stddef.h>
#include <stdint.h>

void shared_arena_init(size_t capacity);
void* shared_arena_alloc(size_t bytes);
void shared_arena_free_all(void);
uint32_t shared_arena_peak_bytes(void);
uint32_t shared_arena_capacity_bytes(void);
```

Create:
```c
// omi/omiGlass/firmware/src/memory/shared_arena.cpp
#include "memory/shared_arena.h"

#include <stdlib.h>

static uint8_t* g_buf = NULL;
static size_t g_cap = 0;
static size_t g_off = 0;
static size_t g_peak = 0;

void shared_arena_init(size_t capacity) {
    free(g_buf);
    g_buf = (uint8_t*)malloc(capacity);
    g_cap = g_buf ? capacity : 0;
    g_off = 0;
    g_peak = 0;
}

void* shared_arena_alloc(size_t bytes) {
    if (!g_buf || bytes == 0) return NULL;
    if (g_off + bytes > g_cap) return NULL;
    void* p = g_buf + g_off;
    g_off += bytes;
    if (g_off > g_peak) g_peak = g_off;
    return p;
}

void shared_arena_free_all(void) { g_off = 0; }
uint32_t shared_arena_peak_bytes(void) { return (uint32_t)g_peak; }
uint32_t shared_arena_capacity_bytes(void) { return (uint32_t)g_cap; }
```

---
---


### Task 6: 先落地“验签接口 + 可测”骨架，再接入真实 OTA 流程

**Files:**
- Create: `omi/omiGlass/firmware/src/ota/ota_image_verify.h`
- Create: `omi/omiGlass/firmware/src/ota/ota_image_verify.cpp`
- Modify: `omi/omiGlass/firmware/src/ota.cpp`（下载完成前后插入 verify + 状态机）
- Test: `omi/omiGlass/firmware/test/test_ota_verify.cpp`

- [ ] **Step 1: failing test（验签接口可被调用，坏签名返回 false）**

Create:
```cpp
// omi/omiGlass/firmware/test/test_ota_verify.cpp
#include <unity.h>
#include "ota/ota_image_verify.h"

void test_verify_rejects_invalid_signature() {
    uint8_t image[4] = {1,2,3,4};
    uint8_t pub[32] = {0};
    uint8_t sig[64] = {0};
    TEST_ASSERT_FALSE(verify_firmware_signature(image, sizeof(image), pub, sig));
}

void setup() {
    UNITY_BEGIN();
    RUN_TEST(test_verify_rejects_invalid_signature);
    UNITY_END();
}

void loop() {}
```

- [ ] **Step 2: 最小实现（Ed25519 verify 调用封装）**

Create:
```c
// omi/omiGlass/firmware/src/ota/ota_image_verify.h
#pragma once

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

bool verify_firmware_signature(
    const uint8_t* image,
    size_t image_size,
    const uint8_t* pubkey,
    const uint8_t* signature
);
```

Create:
```cpp
// omi/omiGlass/firmware/src/ota/ota_image_verify.cpp
#include "ota/ota_image_verify.h"

#include "esp_crypto/ed25519.h"

bool verify_firmware_signature(
    const uint8_t* image,
    size_t image_size,
    const uint8_t* pubkey,
    const uint8_t* signature
) {
    if (!image || !pubkey || !signature) return false;
    return ed25519_verify(pubkey, image, image_size, signature) == 0;
}
```

- [ ] **Step 3: 运行固件单测**

Run:
```bash
cd omi/omiGlass/firmware
platformio test -e seeed_xiao_esp32s3 -f test_ota_verify
```
Expected: PASS。

- [ ] **Step 4: 将 verify 接入 OTA 下载流程（先失败即中止）**

Modify `ota.cpp`：在 `download_and_install_firmware()` 完成下载到 buffer/分区后、调用 `Update.end()` 前插入验签；验签失败走 `OTA_STATUS_INSTALL_FAILED` 并退出。

---

## 7) 代码生成后执行方式

Plan 完成并保存到 `docs/superpowers/plans/2026-04-17-ai-glasses-mvp.md`。两种执行选项：

1. **Subagent-Driven（推荐）**：我按 Task 逐个派发子代理实现与自测，你在每个 Task 完成后 review 决策下一步  
2. **Inline Execution**：我在当前会话直接按 Task 顺序实现并自测（适合快速推进，但每次变更会更大）

请告诉我选择 1 还是 2。
