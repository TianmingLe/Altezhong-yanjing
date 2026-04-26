# Altezhong-yanjing（AI 眼镜）MVP 生产级 Spec（方案 A）

版本：v1.0.0（Spec）  
日期：2026-04-17  
Plan 基准：AI 眼镜 MVP 行动计划方案（飞书）  
基准代码库：BasedHardware/omi（本仓库以其目录与协议为模板）

## 1. 背景与目标

### 1.1 MVP 目标（V1.0）

在“轻眼镜 + 重后端”的前提下，交付一套刷机即可用、可演示、可迭代的生产级代码基线，实现：

- 眼镜端（ESP32‑S3）稳定采集：音频（16kHz）与相机 JPEG（VGA/可配置），并通过 BLE 高吞吐传输到手机
- 手机端（Android/Flutter）完成：设备接入、任务下发、实时预览、遥控操作、算力卸载路由、本地/云端语音识别链路、AR/HUD 叠加预览渲染
- 云端（FastAPI）完成：实时转写入口复用、视觉推理入口（基于帧/特征）、历史数据与告警、固件分发/OTA URL 生成
- 可插拔 PC/Windows 节点：仅提供 relay 接口与帧转发逻辑骨架，不作为强依赖

### 1.2 非目标（V1.0 不做）

- 眼镜端物理显示屏/光波导渲染（MVP 无屏，AR/HUD 在手机端预览实现；但协议与 HAL 必须抽象与预留）
- 360° 多摄阵列与全景实时推理（V2.0）
- 强化学习动态卸载（V2.0）

## 2. 硬件基线对齐与抽象约束

### 2.1 眼镜端硬件（MVP）

主控：ESP32‑S3（参考 [omiGlass/firmware](file:///workspace/omi/omiGlass/firmware)）  
外设：单麦（PDM/I2S，预留双麦接口）、摄像头、音频输出（骨传导/扬声器）、电池与电量检测、按键（开关/重启）、BLE 5.x

### 2.2 抽象一致性（避免协议分裂）

即便 MVP 固件落在 ESP32‑S3，仍需保持与 nRF/Zephyr 路径一致的“上层抽象”：

- **protocols/**：所有 BLE/Task/HUD/OTA 的二进制协议定义统一存放并可被固件/手机/后端复用（生成代码或共享头文件）
- **src/scheduler/**：电量/网络/任务复杂度的规则路由逻辑在“接口层”一致；ESP32 通过适配层提供同名 API
- **src/power/**：统一电源管理接口（进入 idle/sleep、外设休眠、动态降频）；ESP32 映射到其 PM/频率 API
- **src/ota/**：统一 OTA 状态机与签名/回滚策略接口；ESP32 采用等价机制实现 A/B + 回滚超时（见 5.4）

## 3. 总体架构与数据流

### 3.1 模块边界（文字图）

- 眼镜固件（ESP32‑S3）
  - audio：采集 →（RNNoise）→ 编码（Opus/LC3）→ BLE 流
  - vision：采集 →（TFLite Micro 特征/框）→ BLE 上传（特征/低频帧）
  - gatt：OMI 兼容服务 + 新增 Task/HUD/Control/OTA 特征
  - scheduler：任务路由指令接收与最小本地执行（采集、编码、发送、节能策略）
  - power：电量监测、低电量降级、休眠
  - ota：Wi‑Fi OTA 下载与 A/B 切换、回滚
  - display（桩）：不耦合任何驱动，仅暴露 stub（见 5.3）

- 手机 App（Flutter, Android 优先）
  - ble：连接/重连、MTU/PHY 协商、流读取、任务下发
  - audio pipeline：VAD/降噪（可选）→ WS `/v4/listen` → 文字流 → 摘要/指令
  - vision pipeline：JPEG 预览 →（可选）本地特征/压缩 → 上传云端推理 → 告警
  - hud renderer（MVP）：WebSocket HUD 渲染器（手机端叠加预览）
  - router：规则引擎（电量/网络/复杂度）决定本地/手机/云/PC

- 云端后端（FastAPI）
  - stt：复用 `/v4/listen`（见 [transcribe.py](file:///workspace/omi/backend/routers/transcribe.py#L2815-L2854)）
  - vision：新增 `/v1/vision/frame` 与 `/v1/vision/feature`（事件检测/描述/历史分析）
  - ota：复用固件分发与版本索引（见 [firmware.py](file:///workspace/omi/backend/routers/firmware.py#L1-L118)）
  - alert：告警规则、推送到 App（WS/FCM）

- PC/Windows（可插拔）
  - `pc/relay/`：实现 `relay_interface.h` 规定的“帧转发/推理回传”最小能力
    - 协议：WebSocket + JSON 控制帧 + Base64 数据块（MVP 仅支持 feature_vector）
    - 断点续传：`session_init/chunk/session_resume/session_complete` + `missing_ranges`（半开区间 `[start,end)`）

### 3.2 依赖关系图（Mermaid）

```mermaid
flowchart LR
  subgraph Glass[ESP32-S3 Glass Firmware]
    A1[Audio Capture] --> A2[RNNoise*] --> A3[Opus/LC3 Encode] --> GATT1[BLE Audio Notify]
    V1[Camera Capture] --> V2[TFLM Feature Extract*] --> GATT2[BLE Vision Notify]
    V1 --> GATT3[BLE JPEG Notify]
    CTRL[Task/Control RX] --> SCH[Scheduler/Router]
    SCH --> PWR[Power Mgmt]
    OTA[OTA State Machine] --> WIFI[Wi-Fi Download]
    DISP[display_* stubs]
  end

  subgraph Phone[Android (Flutter) App]
    BLE[BLE Manager] --> AUD[Audio Pipeline]
    BLE --> IMG[Image Reassembler + Preview]
    BLE --> HUDTX[HUD WS Client]
    AUD --> STTWS[WS /v4/listen]
    IMG --> VISIONUP[Vision Uploader]
    ROUTER[Rule Router] --> AUD
    ROUTER --> VISIONUP
    ROUTER --> PCRELAY[PC Relay (optional)]
    HUDRENDER[HUD Renderer (MVP)] <-- HUDTX
  end

  subgraph Cloud[FastAPI Backend]
    STTWS --> STT[STT Service]
    VISIONUP --> VISION[Vision Inference]
    VISION --> ALERT[Alert Engine]
    OTAIDX[Firmware Index] --> OTAURL[OTA URL]
  end

  ALERT --> Phone
  OTAURL --> Phone
  Phone -->|BLE| Glass
```

注：带 * 的为“强制集成清单”模块（见第 6 章）。

## 4. 目录结构规划（严格对齐 omi + 新增约定）

### 4.1 固件（ESP32‑S3）

基于 [omiGlass/firmware](file:///workspace/omi/omiGlass/firmware) 目录，新增/调整如下（保留现有文件，增量改造）：

```
omiGlass/firmware/
  src/
    app.cpp / app.h
    main.cpp
    config.h
    gatt/
      omi_gatt_service.{h,cpp}           # OMI 兼容 + 新增特征注册
      gatt_mtu_phy.{h,cpp}               # MTU/PHY/连接参数策略（统一入口）
    audio/
      audio_capture.{h,cpp}              # PDM/I2S 采集抽象
      audio_preprocess.{h,cpp}           # RNNoise 接入点（可开关）
      opus_encoder.{h,cpp}               # 已有，保留
      ble_audio_stream.{h,cpp}           # 音频包头/分片/重传策略
    vision/
      camera_capture.{h,cpp}             # 相机抽象（已存在逻辑可下沉）
      jpeg_stream.{h,cpp}                # JPEG 分片与帧边界
      feature_extract_tflm.{h,cpp}        # TFLite Micro 接入点（特征/框输出）
    scheduler/
      task_router.{h,cpp}                # 任务解析、路由执行（采集/发送/休眠）
      policy_rules.{h,cpp}               # 电量/网络/复杂度规则
    power/
      power_manager.{h,cpp}              # 统一 PM 接口，映射 ESP32
      battery_monitor.{h,cpp}            # 复用现有电池逻辑
    ota/
      ota_manager.{h,cpp}                # 统一 OTA 状态机
      ota_transport_wifi.{h,cpp}          # BLE 下发 Wi-Fi + URL → 下载
      ota_image_verify.{h,cpp}            # 签名校验与回滚策略（见 5.4）
    display/
      display_hal.h                       # 仅桩函数与接口类型
      display_hal.cpp                     # 空实现（严禁耦合驱动）
  protocols/
    ar_hud_protocol.h
    task_protocol.h
    ble_gatt_table.h
    ota_protocol.h
```

约束：

- `protocols/` 必须同时能被固件（C/C++）与手机/后端（通过代码生成或镜像定义）使用
- `display/` 仅允许 stub，不允许包含 SPI/I2C/具体驱动依赖

### 4.2 手机 App（Flutter）

基于 [app](file:///workspace/omi/app) 目录，新增：

```
app/lib/
  services/
    hud/
      hud_protocol.dart                   # HUD 二进制帧编解码（≤64B）
      hud_ws_client.dart                  # 连接本地 HUD 渲染 WS
      hud_overlay_controller.dart         # 将 HUD 帧映射到预览叠加
    router/
      task_router.dart                    # 规则引擎（电量/网络/复杂度）
      task_models.dart                    # Task/Result 模型（与 task_protocol 对齐）
    vision/
      frame_uploader.dart                 # JPEG/特征上传后端
      event_subscriber.dart               # 告警订阅与提示
  android/
    app/src/main/cpp/whisper/             # whisper.cpp 集成点（可选构建）
```

### 4.3 后端（FastAPI）

基于 [backend](file:///workspace/omi/backend) 目录，新增：

```
backend/routers/
  vision.py                               # /v1/vision/frame /feature
  hud.py                                  # (可选) HUD 帧转发/多端同步
backend/services/
  vision/                                 # 推理与规则封装
  router/                                 # 任务路由辅助（云端策略）
backend/tests/
  test_vision_api.py
  test_task_protocol.py
```

### 4.4 PC/Windows（可插拔）

新增独立目录（不强依赖构建进主链路）：

```
pc/
  relay/
    relay_interface.h
    relay_server.py                       # 最小 WS/TCP 帧转发（可替换为 Rust）
    tests/
```

## 5. 核心协议定义

### 5.1 BLE GATT 服务表（基于 OMI）

MVP 必须兼容现有 OMI Glass 协议（见 [config.h](file:///workspace/omi/omiGlass/firmware/src/config.h#L148-L186) 与 [models.dart](file:///workspace/omi/app/lib/services/devices/models.dart#L18-L75)）。

#### 5.1.1 已有（必须保持）

Service：`OMI_SERVICE_UUID = 19B10000-E8F2-537E-4F6C-D104768A1214`  

| Characteristic | UUID | 方向 | 属性 | 说明 |
|---|---|---|---|---|
| Audio Data | `...0001...` | Glass → Phone | Notify | 音频流，3B header + codec payload |
| Audio Codec | `...0002...` | Glass → Phone | Read | 1B codec id（21=Opus FS320 V1，22=Opus FS320 V2(seq+timestamp)）|
| Photo Data | `...0005...` | Glass → Phone | Notify/Read | JPEG 分片流 |
| Photo Control | `...0006...` | Phone → Glass | Write | 触发拍照/控制（按现有实现）|

Battery Service：`0x180F` / Battery Level：`0x2A19`

OTA Service：`19B10010-E8F2-537E-4F6C-D104768A1214`  
Control：`...0011...`（Write/Read） Data：`...0012...`（Notify）

#### 5.1.2 新增（V1.0 扩展，不破坏兼容）

仍使用 `19B100xx-...` 命名空间，避免服务碎片化；手机端按“发现服务后按 UUID 是否存在启用特性”的方式兼容旧固件。

| Feature | UUID | 方向 | 属性 | 负载上限 |
|---|---|---|---|---|
| Task Control | `19B10020-E8F2-537E-4F6C-D104768A1214` | Phone → Glass | Write Without Response | ≤ (MTU-3) |
| Task Event | `19B10021-E8F2-537E-4F6C-D104768A1214` | Glass → Phone | Notify | ≤ (MTU-3) |
| HUD Frame Out | `19B10022-E8F2-537E-4F6C-D104768A1214` | Glass → Phone | Notify | **≤64B/帧**（硬约束） |
| Device Control | `19B10023-E8F2-537E-4F6C-D104768A1214` | Phone → Glass | Write | ≤ (MTU-3) |

BLE 链路参数硬要求：

- MTU：**251**（优先保证跨机型稳定；若协商更大可用，但协议不得依赖 >251）
- PHY：2M（若不可用则回退 1M，需上报 Task Event）
- 音频 Notify：高优先级、禁止与 JPEG 大流量同频抢占（由 scheduler 控制节流）

### 5.2 音频流协议（BLE Audio Streaming）

#### 5.2.1 编码与采样

- 采样：16kHz，单声道
- 编码：Opus（frame=320 samples/20ms，参照 [config.h](file:///workspace/omi/omiGlass/firmware/src/config.h#L134-L147)）
  - codec id=21：V1 包头（3B header）
  - codec id=22：V2 包头（6B header：seq+采集时间戳）
- 预处理：RNNoise（可开关，见第 6 章约束）

#### 5.2.2 包格式

V1（codec id=21）每条 BLE 通知：`[packet_id_lo, packet_id_hi, sub_index] + encoded_payload`  
V2（codec id=22）每条 BLE 通知：`[seq(2B) + timestamp_ms(4B) + encoded_payload]`  
手机端剥离 header（见 [ble_device_source.dart](file:///workspace/omi/app/lib/services/audio_sources/ble_device_source.dart#L4-L44)）。

约束：

- `AUDIO_PACKET_HEADER_SIZE = 3`
- `sub_index` 用于一帧 Opus 被拆分多个 BLE 包时的顺序（固件按 MTU 分片）
- 手机端以 header 作为 sync key，对丢包/乱序做容错（V1.0：不做重传，仅统计与告警）
  - V2 的 `timestamp_ms` 必须来自采集时刻（在 `onMicData()` 采样点捕获并沿 pipeline 透传），禁止使用“发送时刻”或“编码完成时刻”
  - V2 的 `seq` 为 uint16，回绕 65535→0；接收端丢包判断需处理回绕
  - 固件侧拥塞节流：当滚动 1s 带宽窗口 `tx_bytes_1s*8 > 400kbps`，暂停 JPEG 分片发送，优先保障音频（埋点：`BLE_AUDIO_BW`）

### 5.3 AR/HUD 二进制帧协议（MVP：手机端渲染）

#### 5.3.1 ar_hud_protocol.h（HAL）

MVP 强制采用分层抽象：

- 固件端只产生 HUD 二进制帧，不渲染
- 固件端严禁耦合任何显示驱动
- SPI/I2C 仅保留 stub 接口

接口（桩函数）：

```c
void display_init(void);
void display_render(const hud_frame_t* f);
void display_clear(void);
```

#### 5.3.2 HUD 帧结构（≤64 字节/帧）

眼镜端输出帧格式（你指定的字段顺序与大小）：

```
| type(1B) | priority(1B) | x(2B) | y(2B) | text_len(1B) | payload(N) |
N = text_len，且 total_len = 7 + N ≤ 64
```

字段定义：

- type：HUD 元素类型（0=text, 1=icon, 2=toast, 3=alert）
- priority：0~255（越大越高）；手机渲染器按优先级合并/抢占
- x/y：uint16，小端，手机端坐标系为预览画面像素坐标（以预览宽高归一映射亦可，但必须在协议中固定一种方式；V1.0 固定为像素坐标）
- payload：
  - type=text：UTF‑8 字符串（最大 57B）
  - type=icon：后续扩展为 1B icon_id + 颜色/大小 TLV（V1.0 仅预留）

数据流（MVP）：

Glass `HUD Frame Out (BLE)` → Phone → `HUD WebSocket` → Phone HUD Renderer（叠加到相机预览 / 信息面板）→ 必要时 TTS 播报

#### 5.3.3 Vision Feature Notify（codec id=33）

- `FEATURE_CODEC_ID=33`：表示“视觉特征向量”数据流（int8 embedding），用于手机端/云端做相似度、检索或事件检测
- Feature Notify Payload（每条 BLE 通知固定 134B）：
  - `[seq(2B) + timestamp_ms(4B) + features(128B)]`
  - `seq`：uint16，小端，回绕 65535→0
  - `timestamp_ms`：uint32，小端；MVP 阶段可先用 `millis()`，后续替换为相机帧捕获时间戳
  - `features`：128×int8（量化后特征向量）
- Feature Quant Read Payload（固定 6B）：
  - `[scale(4B float32 little-endian) + zero_point(1B int8) + model_id(1B uint8)]`

#### 5.3.4 PC Relay Frame Header（跨链路复用）

- PC Relay 传输层：WebSocket + JSON 控制帧 + Base64 数据块（见 `pc/relay/`）
- RelayFrameHeader（用于在 “Phone → PC Relay” 场景复用 `FEATURE_CODEC_ID=33` 的语义）：
  - `frame_type`：`0x02` 表示 feature_vector（MVP）
  - `codec_id`：`33`（与固件 `FEATURE_CODEC_ID=33` 对齐）
  - `seq_le/timestamp_ms_le`：与 BLE Feature Header 相同语义，小端，`seq` 回绕 65535→0
  - `payload_len_le`：payload 字节数（feature-only 为 128）

### 5.4 OTA 协议与回滚（统一接口 + ESP32 等价实现）

#### 5.4.1 BLE 下发 Wi‑Fi + URL（兼容 OmiGlass）

沿用现有 OTA service（见 [config.h](file:///workspace/omi/omiGlass/firmware/src/config.h#L161-L186)），命令格式：

- `OTA_CMD_SET_WIFI = 0x01`：`[cmd, ssid_len, ssid..., pass_len, pass...]`
- `OTA_CMD_START_OTA = 0x02`：`[cmd, url_len, url...]`
- `OTA_CMD_GET_STATUS = 0x04`：请求状态

状态通过 `OTA_DATA_UUID` Notify：`[status_code, progress?]`

#### 5.4.2 签名与 A/B 分区、5s 回滚超时（生产要求）

统一 OTA 策略接口（固件 `ota_manager`）要求：

- A/B 分区：下载到非活动分区
- 镜像签名校验：在切换前完成（签名算法以“已评审方案”为准；V1.0 以 Ed25519 或 ECDSA-P256 二选一落地，最终以仓库既有实现/批准为准）
- 回滚：新镜像启动后 **5 秒**内必须设置“boot ok”标志，否则自动回滚到旧镜像

实现约束：

- nRF/Zephyr 路径：使用 **MCUboot**（作为目标一致性标准）
- ESP32‑S3 路径：采用 **ESP-IDF OTA + app rollback** 实现等价语义；接口命名、状态码与日志事件与 MCUboot 对齐，避免上层协议分裂

备注：本 Spec 不引入未评审三方依赖。若签名验证需要加密库，必须优先使用现有平台 SDK 内置能力或“已评审模块清单”中的实现。

### 5.5 Task 路由消息格式（Phone ↔ Glass）

目的：统一“任务下发、取消、ACK、结果/告警”通道，使手机、后端、PC 节点可复用同一消息模型。

#### 5.5.1 传输层

- BLE：`Task Control`（写入）与 `Task Event`（通知）
- WS（手机 ↔ HUD 渲染器/后端）：二进制帧透传相同消息体

#### 5.5.2 二进制消息头

固定头（小端）：

```
| ver(1) | msg_type(1) | flags(1) | reserved(1) | task_id(4) | payload_len(2) | crc16(2) | payload(...) |
```

- ver：协议版本（V1.0=1）
- msg_type：
  - 0x01 TASK_SUBMIT
  - 0x02 TASK_CANCEL
  - 0x03 TASK_ACK
  - 0x04 TASK_RESULT
  - 0x05 TASK_EVENT（告警/状态）
- flags：bit0=needs_ack，bit1=high_priority，bit2=encrypted（V1.0 预留）
- task_id：uint32（手机生成，单设备内递增）
- payload：TLV（见下）
- crc16：对 header（不含 crc16 字段）+ payload 的 CRC16-CCITT

#### 5.5.3 Payload（TLV）

```
| t(1B) | l(1B) | v(l bytes) | ...
```

基础字段：

- t=0x01 task_kind（1B）：0x01 audio_stream, 0x02 photo_stream, 0x03 feature_stream, 0x04 hud_push, 0x05 ota, 0x06 device_ctrl
- t=0x02 complexity（1B）：0~10（手机路由器用于卸载决策）
- t=0x03 deadline_ms（4B）
- t=0x04 params（N）：子 TLV（例如拍照间隔、JPEG 质量、音量、VAD 阈值）

路由器规则引擎输入：

- 电量：眼镜上报（battery % + 电压）与手机估算
- 网络：手机当前链路（BLE only / Wi‑Fi / LTE）
- 任务复杂度：由任务提交方填入或由手机估算

输出：

- execute_on：glass / phone / cloud / pc（V1.0 pc 仅预留）
- 降级策略：降帧率、关相机、关 RNNoise、关本地 ASR 等

## 6. 开源模块强制集成清单（位置与约束）

以下 6 个模块被视为“已评审依赖”，允许引入；其它第三方依赖禁止新增。

### 6.1 RNNoise for Pico2（音频预处理）

- 集成位置：`omiGlass/firmware/src/audio/audio_preprocess.*` + `third_party/rnnoise/`（或 `src/audio/rnnoise/`）
- 约束：
  - INT8 量化路径
  - RAM ≤ 40KB（静态 + 运行时峰值）
  - 可通过编译开关关闭（低电量/高负载降级）

### 6.2 Zephyr TFLite Micro（视觉特征提取）

- 集成位置：`omiGlass/firmware/src/vision/feature_extract_tflm.*` + `third_party/tflite-micro/`
- 约束：
  - Arena ≤ 30KB
  - 输出仅允许：
    - 128 维特征向量（INT8 或 FP16，V1.0 固定一种并写入协议）
    - 或边界框（最多 K=10 个，量化坐标）
  - 不在眼镜端跑大模型，只做轻量特征/框

### 6.3 whisper.cpp（手机端离线 ASR / 备用 ESP32 离线）

- 集成位置（手机端优先）：`app/android/app/src/main/cpp/whisper/`（通过 FFI/Platform Channel）
- 约束：
  - 模型：tiny
  - 启用方式：触发式（网络不可用或隐私模式）
  - 默认路径仍为云端 `/v4/listen`

### 6.4 nRF/ESP BLE Audio Streaming（GATT 音频服务）

- 集成位置：
  - 固件：`src/audio/ble_audio_stream.*` + `src/gatt/omi_gatt_service.*`
  - 手机：沿用 `flutter_blue_plus` 通道与现有 `BleDeviceSource` 头剥离逻辑
- 约束：
  - MTU=251，2M PHY（尽力协商）
  - Codec：LC3/Opus（V1.0 默认 Opus，LC3 作为扩展）

### 6.5 Zephyr Power Management（调度器底层）

- 集成位置：
  - 抽象接口：`omiGlass/firmware/src/power/power_manager.*`
  - Zephyr 版本实现：`firmware_zephyr/`（本仓库 V1.0 不强制实现完整 Zephyr 固件，但接口必须预留）
  - ESP32 实现：映射到 ESP32 的 DFS/Light Sleep API
- 约束：动态降频/外设休眠策略由 `scheduler/policy_rules` 统一控制

### 6.6 MCUboot（OTA 签名升级）

- 集成位置：
  - 抽象接口：`omiGlass/firmware/src/ota/ota_manager.*` + `ota_image_verify.*`
  - Zephyr/nRF 路径：MCUboot
  - ESP32 路径：等价 A/B + rollback（接口对齐 MCUboot 语义）
- 约束：5s 回滚硬超时（必须在固件中强制）

## 7. 安全与可靠性要求（V1.0）

- BLE：默认要求配对绑定（LESC），未绑定设备禁止下发 OTA 与高权限 Device Control
- OTA：必须签名校验 + A/B + 回滚；失败必须能回到上一版本
- 断点续传：
  - OTA 下载：HTTP Range（若后端/存储支持）
  - 历史帧/日志上传：分块 + 校验 + 续传（V1.0 先实现协议与骨架）
- 噪声环境语音指标：
  - 本地唤醒词 + VAD 降噪作为架构能力预留；硬指标（85dB 唤醒率/识别准确率）列入验收但允许以“实验室复现实测”为准

## 8. 验收用例（含硬指标与测试命令）

### 8.1 固件（ESP32‑S3）

硬指标（V1.0）：

- 音频链路：BLE → 手机端解码可连续播放/转写，**丢包率 < 1%**（5 分钟窗口）
- 图像链路：VGA JPEG 分片重组成功率 **≥ 99%**（100 帧）
- HUD：单帧 ≤64B，手机端渲染延迟 p95 **≤ 150ms**（从 BLE 收到到 UI 呈现）
- 内存：
  - RNNoise 路径峰值 RAM **≤ 40KB**
  - TFLM Arena **≤ 30KB**
- 功耗：在 500mAh 电池假设下，默认配置连续运行 **≥ 6 小时**（目标平均电流 ≤ ~80mA）

测试命令（以 PlatformIO 为基准）：

```bash
cd omi/omiGlass/firmware
platformio run -e seeed_xiao_esp32s3
platformio run -e seeed_xiao_esp32s3 -t size
platformio test -e seeed_xiao_esp32s3
```

功耗测试方法（需要硬件仪器）：

- USB 电流表/电源分析仪记录 10 分钟窗口平均电流与峰值电流
- 分别测试：仅 BLE + 音频、BLE + 音频 + 相机、低电量降级模式

### 8.2 手机端（Flutter/Android）

硬指标（V1.0）：

- 连接：BLE 断链后 **10s 内自动重连**（Android 前台）
- 转写：网络良好时，语音到首个文字片段延迟 p95 **≤ 1.2s**
- 离线：启用 whisper.cpp 后，触发式转写可输出结果（不要求实时流式）

测试命令：

```bash
cd omi/app
flutter test
```

### 8.3 后端（FastAPI）

硬指标（V1.0）：

- `/v4/listen`：稳定处理 16kHz Opus（codec=opusFS320）上行；断连具备重连容错
- `/v1/vision/frame`：在 640x480 @1fps 的输入下，事件响应 p95 **≤ 2.5s**（以部署实例测为准）

测试命令：

```bash
cd omi/backend
python -m pytest
```

## 9. Trae Solo 分阶段实现清单（优先级/依赖/每日检查点）

说明：

- P0：必须完成，才能形成“刷机可用闭环”
- P1：增强能力（告警、路由更完整、离线能力）
- P2：预留/骨架（PC 节点、断点续传完善）

### 9.1 阶段与依赖顺序

**阶段 0（P0）基线可构建**

- 固件：保持现有 `omiGlass/firmware` 可编译/可刷写/可连接
- App：可连接 OMI Glass，能收到音频与图片流（复用现有逻辑）
- 后端：本地可启动，`/v4/listen` 可用

**阶段 1（P0）协议与目录落地**

- 新增 `protocols/`（HUD/Task/BLE 表/OTA）并在固件与 App 引用
- 新增 BLE 新特征（Task/HUD/Device Control）但保持旧固件兼容

**阶段 2（P0）任务路由最小闭环**

- App 侧规则引擎：决定执行位置（phone/cloud）并能下发 Task
- 固件侧 task_router：解析任务、控制采集/节流/低电量降级

**阶段 3（P0）AR/HUD（手机渲染）**

- HUD 二进制帧 BLE 输出（≤64B）
- 手机 HUD 叠加预览与提示音/语音播报

**阶段 4（P1）视觉事件告警**

- 后端 vision API（帧/特征入口）
- 手机端订阅告警并推送 HUD

**阶段 5（P1）音频预处理与离线 ASR**

- RNNoise 接入点（可开关）
- whisper.cpp Android 集成（触发式）

**阶段 6（P0）生产 OTA（签名 + A/B + 回滚）**

- 统一 OTA 状态机（兼容现有 BLE 下发 Wi‑Fi + URL）
- ESP32 等价 A/B 与 5s 回滚硬超时
- 后端 OTA URL/版本链路打通

**阶段 7（P2）PC Relay 骨架 + 断点续传骨架**

- `relay_interface.h` + 最小帧转发 server
- 上传/下载分块协议与 Range 支持（骨架）

### 9.2 每日检查点（示例节奏，按完成度推进）

- Day 1：阶段 0 全链路可本地跑通（固件编译+App 连接+后端启动）
- Day 2：阶段 1 `protocols/` 与 BLE 新特征打通（能收发 Task/HUD 空帧）
- Day 3：阶段 2 任务下发→固件执行→回传 ACK/事件（最小任务集：start/stop audio, capture photo）
- Day 4：阶段 3 HUD 端到端（≤64B 帧）+ 手机叠加预览
- Day 5：阶段 4 后端 vision API + 手机告警订阅（至少 1 类事件）
- Day 6：阶段 6 OTA 签名/回滚机制在 ESP32 跑通（可回滚验证）
- Day 7：补齐测试、功耗/内存基线报告与回归脚本

## 10. 质量门禁（生产级标准）

- 不新增未评审三方依赖；已评审模块以第 6 章为准
- 每个新增模块必须：
  - 提供单元测试（固件：PlatformIO Unity；App：flutter test；后端：pytest）
  - 给出内存占用（编译产物 size + 运行时峰值）与功耗影响预估/测量方法
- 协议必须二进制、版本化、可向后兼容（旧固件/旧 App 允许功能降级但不得崩溃）

## 附录 A：执行约束与补充信息清单（评审确认）

### A.1 g4 UI/UX 设计令牌（强制）

- 配色
  - 主 HUD：`#00E5FF`
  - 告警/Alert：`#FF3D00`
  - 背景遮罩：`#000000`，opacity `0.4`
- 排版
  - 系统默认无衬线字体
  - HUD 文字：`14sp`，行高 `1.2`
  - 最大宽度：`80vw`，超出省略号 `...`
- 动效
  - 入场：`SlideTransition`，Y 轴偏移 `0.1h`，时长 `100ms`
  - 退场：`Opacity` 渐变，时长 `120ms`
  - 总渲染链路需满足 Spec 8.2：`p95 ≤ 150ms`，动效不得阻塞主线程
- 坐标原点
  - `(0,0)` 对应相机预览左上角
  - 必须适配 `BoxFit.cover` 的裁剪偏移，禁止硬编码屏幕宽高

### A.2 无硬件模拟方案（调试必备）

- 固件端 Mock（后续固件任务落地）
  - 在 `omiGlass/firmware/src/app.cpp` 增加 `HUD_MOCK_MODE` 开关
  - 启用后通过 FreeRTOS 定时器每 `2s` 调用 `send_hud_frame()` 发送循环测试帧（type=0/2/3 轮询，x/y 固定 `320/240`）
- 手机端 Mock（g4 落地）
  - `hud_protocol.dart` 暴露 `enableMockStream(bool)`，开启后跳过 BLE 注入模拟帧，便于 UI 独立调试
- 验证命令
  - `flutter run --debug` + 模拟器/真机，确认优先级覆盖与 3s 自动消退

### A.3 Vision API 契约（Phase 4 前置定义）

- 接口：`POST /v1/vision/frame`
- 输入：`multipart/form-data`
  - `image`: JPEG binary（VGA 640x480，quality=75）
  - `metadata`: JSON string `{ "timestamp": 1713369600000, "battery": 85, "task_id": "uuid" }`
- 输出（200 OK）

```json
{
  "events": [
    { "type": "person_detected", "confidence": 0.92, "bbox": [120, 80, 200, 300] }
  ],
  "processing_time_ms": 145,
  "router_decision": "cloud"
}
```

- 约束：后端需实现基础事件去重（5s 内同 bbox 合并），避免告警风暴

### A.4 OTA 密钥管理与降级阈值（Phase 6/2 精确值）

- 密钥工作流
  - 开发环境：私钥 `keys/dev/ota_sign.pem`（`.gitignore` 排除），公钥 `keys/dev/ota_verify.pub` 硬编码进固件
  - 签名脚本：`scripts/sign_ota.sh` 输出 `firmware.bin` + `firmware.sig`，CI 通过环境变量注入生产密钥
- 降级阈值（policy_rules）
  - 网络降级：BLE RTT `>200ms` 或丢包率 `>5%` 持续 `10s` → JPEG 降至 `1fps`，HUD 仅保留 `priority≥200`
  - 离线 ASR 触发：连续 `3` 次 `/v4/listen` 超时（`>3s`）或 `privacy_mode=true` → 切换 `whisper.cpp` tiny
  - 电量降级：`battery < 20%` → 关闭相机采集，仅保留音频流 + 心跳
