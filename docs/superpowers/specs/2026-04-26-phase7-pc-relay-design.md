# Phase 7：PC Relay 骨架 + 断点续传（WS + JSON + Base64）

日期：2026-04-26  
范围：主仓库 `pc/relay/`（可插拔算力节点）  
目标：提供“眼镜/手机 → PC Relay（WS）→ 推理/处理 → 结果回传”的最小可运行闭环，并提供断点续传协议骨架（MVP）。

## 1. 背景与动机

Phase 1-3 已完成固件端音频与视觉特征流（Feature Notify 134B + Quant 6B）并通过门禁。Phase 7 的目标是在 PC 侧提供一个“可插拔算力节点”骨架，用于：

- 验证多跳链路（Glass/Phone → PC）可工作
- 验证断点续传的状态机与协议字段合理
- 为后续 JPEG chunk 中继（frame_type=0x01）与更高性能传输（TCP / 二进制帧）预留扩展点

## 2. 设计原则（MVP）

- **优先 feature-only**：MVP 仅实现 `frame_type=0x02 feature_vector`，避免 JPEG 大流量干扰协议正确性验证。
- **跨语言易解析**：使用 **WebSocket + JSON 控制帧 + Base64 数据块**，降低 Flutter/Python/C++ 的解析成本。
- **可复现**：PC relay 依赖通过 `pc/relay/requirements.txt` 固化，测试与 demo 可一键跑通。
- **协议一致性**：与固件 `protocols/ble_feature_protocol.h` 风格对齐（小端、seq 回绕语义、timestamp 语义）。
- **先骨架后优化**：MVP 不做持久化、不做多客户端调度、不做鉴权；明确记录限制与后续工作。

## 3. 目录结构（交付物）

主仓库新增：

```
pc/
  relay/
    relay_interface.h
    relay_server.py
    requirements.txt
    protocols/
      relay_protocol.h
    tests/
      test_relay_protocol.cpp
      test_relay_server.py
    demo/
      send_feature.py
      resume_session.py
    README.md
    KNOWN_LIMITATIONS.md
```

## 4. 协议设计

### 4.1 传输层

- WebSocket server：`ws://localhost:8766`
- 连接生命周期：单连接可上传多个 session；允许断连重连后 resume 同一 session（MVP：仅内存态）。

### 4.2 数据帧头（RelayFrameHeader）

该头用于描述“一个完整帧”的元数据；帧内容在 session 中按 chunk 上传。

```c
struct RelayFrameHeader {
  uint8_t  frame_type;        // 0x01=jpeg_chunk, 0x02=feature_vector (MVP 实现 0x02)
  uint8_t  codec_id;          // 对齐固件：33=feature, 22=audio_v2（预留）
  uint16_t seq_le;            // 小端，uint16 回绕
  uint32_t timestamp_ms_le;   // 小端，MVP 可用 millis()
  uint32_t payload_len_le;    // 小端，payload 长度（bytes）
};
```

约束：
- `seq_le` 的回绕语义与固件一致：65535→0；上层做丢包/乱序统计时需处理回绕。
- `payload_len_le` 对 feature-only 固定为 128（int8 embedding），但仍保留可变长度以支持后续扩展。

### 4.3 会话与分块（Session + Chunk）

**会话**表示一次“整帧上传”的生命周期。MVP 固定 `chunk_size=512B`，但协议中不强制，允许最后一块不足 512。

#### 4.3.1 Session Init

client → relay：

```json
{"op":"session_init","session_id":"uuid","frame_type":2,"total_bytes":N}
```

relay → client：

```json
{"op":"session_ack","session_id":"uuid","accepted":true}
```

语义：
- `total_bytes` 为“帧头 + payload”的总长度（或仅 payload 的总长度，二选一必须固定）。
- MVP 选择：`total_bytes` = `sizeof(RelayFrameHeader) + payload_len`，便于完整性校验与未来支持 jpeg chunk。

#### 4.3.2 Chunk Upload

client → relay：

```json
{"op":"chunk","session_id":"uuid","offset":X,"data":"<base64>","crc32":Y}
```

relay → client：

```json
{"op":"chunk_ack","session_id":"uuid","offset":X,"next_offset":X+len}
```

约束：
- `offset` 为该 chunk 在 session buffer 中的起始位置（0..total_bytes-1）。
- `crc32` 为该 chunk data 的 CRC32（仅覆盖本 chunk 原始 bytes，不覆盖 JSON）。
- 服务端必须拒绝越界 chunk（offset + len > total_bytes）。

#### 4.3.3 Session Resume

client → relay：

```json
{"op":"session_resume","session_id":"uuid","last_ack_offset":X}
```

relay → client：

```json
{"op":"session_state","session_id":"uuid","received_bytes":X,"missing_ranges":[[start,end],...]}
```

语义：
- `missing_ranges` 为闭区间或半开区间必须固定一种。
- MVP 选择：半开区间 `[start, end)`（Python/多数实现更自然）。

#### 4.3.4 Session Complete

client → relay：

```json
{"op":"session_complete","session_id":"uuid","sha256":"..."}
```

语义：
- MVP：`sha256` 字段保留但可不强制校验（记录 TODO）。
- MVP 必须至少完成：收到 complete 后检查 `missing_ranges` 为空、并可选校验整帧 crc32/sha256（先做结构校验）。

### 4.4 结果回传（Result）

relay → client：

```json
{"op":"result","session_id":"uuid","result_type":"feature_sim","payload":{...}}
```

语义：
- result 为异步消息：可能在 `session_complete` 之后的任意时刻返回。
- MVP：server 直接返回 mock 结果，例如 `{"similarity": 0.92}`。

## 5. 状态机（Server 视角）

对每个 session：

- `NEW`：尚未 init
- `ACTIVE`：已 init，接受 chunk
- `COMPLETE_PENDING`：收到 complete，等待补齐缺失 chunk
- `DONE`：已通过完整性检查（或结构检查），触发 result
- `ERROR`：非法 offset / crc32 错误 / session_id 未知等

关键规则：
- `session_complete` 到达时若仍缺失 chunk，返回 `session_state`（missing_ranges 非空），client 需补齐后再 complete 或 server 自动在补齐后触发结果（MVP 选择：要求 client 再次发送 complete）。

## 6. 内存会话策略（MVP）

- 用 `dict[session_id] -> SessionState` 保存：
  - `total_bytes`
  - `received_ranges`（区间集合）
  - `buffer`（bytearray，长度 total_bytes）
  - `last_activity_ts`
- 清理策略（MVP）：简单超时清理（例如 10 分钟无活动自动删除）；写入 KNOWN_LIMITATIONS。
- 不持久化：重启即丢失；生产级可用 Redis/文件持久化扩展（Phase 7 不实现）。

## 7. 测试策略

### 7.1 C/C++ 协议单测（Unity）

`tests/test_relay_protocol.cpp`：
- 验证 `RelayFrameHeader` 编解码（字段小端序正确、长度正确）
- 验证 `seq` 回绕逻辑（65535→0）相关 helper（若存在）

### 7.2 Python pytest（断点续传）

`tests/test_relay_server.py` 覆盖：
- 正常流程：init → chunk(全量) → complete → 收到 result
- 断点续传：init → chunk(部分) → 断连 → resume → state(missing_ranges) → 补齐 → complete → result

## 8. Demo 与可复现性

### 8.1 依赖

`pc/relay/requirements.txt`（MVP）：
- `websockets`
- `pytest`（可选：若仓库已有测试体系，可仅在文档中说明）

### 8.2 Demo 脚本

- `demo/send_feature.py`：生成 128B int8 feature + RelayFrameHeader → 分块发送 → complete → 打印 result
- `demo/resume_session.py`：发送部分 chunk 后断开 → 重连 resume → 补齐 → complete → 打印 result

README 必须提供 3 步命令：启动 server → 发送 1 帧 → 模拟续传。

## 9. 已知限制（MVP）

- 无鉴权：WS 未做 token/JWT，生产环境需补齐（记录在 `KNOWN_LIMITATIONS.md`）
- 单客户端假设：MVP 只保证单客户端逻辑可用，多客户端需要 `client_id` 与隔离策略
- 会话内存态：server 重启会丢失 session
- 仅实现 feature-only：jpeg_chunk 仅预留 frame_type，暂不实现

